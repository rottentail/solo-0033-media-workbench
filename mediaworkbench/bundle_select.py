"""Allocate a shared byte budget to complete offline projects, not single clips."""


def choose(projects, sizes, capacity):
    if type(capacity) is not int or capacity < 0:
        raise ValueError('media capacity must be a nonnegative integer')
    if len(projects) > 16:
        raise ValueError('at most sixteen candidate projects are supported')
    if any(type(n) is not int or n <= 0 for n in sizes.values()):
        raise ValueError('rendition sizes must be positive integers')
    identities = [p['id'] for p in projects]
    if len(set(identities)) != len(identities):
        raise ValueError('candidate projects must be unique')
    required = [frozenset(p['required']) for p in projects]
    if any(not group or not group <= sizes.keys() for group in required):
        raise ValueError('every project requires available media')
    if any(type(p['priority']) is not int or p['priority'] <= 0 for p in projects):
        raise ValueError('project priorities must be positive integers')
    # Every useful package is the union of one or more whole projects. Shared
    # renditions consume bytes once; selecting them can complete other projects.
    unions = {frozenset(): 0}
    for group in required:
        for previous, cost in list(unions.items()):
            combined = previous | group
            if combined not in unions:
                total = cost + sum(sizes[key] for key in group - previous)
                if total <= capacity:
                    unions[combined] = total
    best = (0, 0, (), ())
    for media, cost in unions.items():
        covered = tuple(sorted(p['id'] for p, group in zip(projects, required) if group <= media))
        value = sum(p['priority'] for p in projects if p['id'] in covered)
        candidate = (-value, cost, covered, tuple(sorted(media)))
        if candidate < best:
            best = candidate
    return {'project_ids': list(best[2]), 'media': list(best[3]),
            'value': -best[0], 'media_bytes': best[1]}
