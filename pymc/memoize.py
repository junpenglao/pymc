import functools

def memoize(obj):
    """
    An expensive memoizer that works with unhashables
    """
    cache = obj.cache = {}

    @functools.wraps(obj)
    def memoizer(*args, **kwargs):
        key = (hashable(args), hashable(kwargs))
        if key not in cache:
            print "miss"
            cache[key] = obj(*args, **kwargs)
        else:
            print "hit"
        return cache[key]
    return memoizer

def hashable(a):
    """
    Turn some unhashable objects into hashable ones.
    """
    if isinstance(a, dict): 
        return hashable(a.iteritems())
    try:
        return tuple(map(hashable,a))
    except:
        return a
