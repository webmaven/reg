class MapKey(object):
    """A map key that can have parents.
    """
    def __init__(self, key, parents=()):
        self.key = key
        self.parents = tuple(parents)
        # we need Python's mro, but we don't have classes. We create
        # some with the same structure as our parent structure. then we
        # get the mro
        self._mro_helper = type('fake_type',
                                tuple(parent._mro_helper for
                                      parent in parents),
                                {'mapkey': self})
        # we then store the map keys for the mro (without the last
        # entry, which is always object)
        self.ancestors = [
            base.mapkey for base in self._mro_helper.__mro__[:-1]]

    def __hash__(self):
        return hash(self.key)

    def __eq__(self, other):
        return self.key == other.key

    def __repr__(self):
        return "<MapKey: %r>" % self.key

class Map(dict):
    """special map that understands about keys in a dag.
    
    A normal mapping (dictionary) in Python has keys that are
    completely independent from each other. If you look up a
    particular key, either that key is present in the mapping or not
    at all.

    This is a mapping that understands about relations between
    keys. Keys can have zero or more parents; they are in a directed
    acyclic graph. If a key is not found, a value will still be found
    if a parent key can be found.
    """
    # sometimes we want to look up things exactly in the underlying
    # dictionary
    exact_getitem = dict.__getitem__
    exact_get = dict.get
    
    def __getitem__(self, key):
        for mapkey in key.ancestors:
            try:
                return self.exact_getitem(mapkey)
            except KeyError:
                pass
        raise KeyError(key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def all(self, key):
        for mapkey in key.ancestors:
            try:
                yield self.exact_getitem(mapkey)
            except KeyError:
                pass

class MultiMapKey(object):
    def __init__(self, *keys):
        self.arity = len(keys)
        self.keys = keys

    def __repr__(self):
        return "<MultiMapKey: %r>" % (self.keys,)

    def __eq__(self, other):
        return self.keys == other.keys

    @property
    def ancestors(self):
        return multimapkey_ancestors(self.keys)
    
def multimapkey_ancestors(keys):
    if not keys:
        yield MultiMapKey()
        return
    first = keys[0]
    rest = keys[1:]
    if not rest:
        for ancestor in first.ancestors:
            yield MultiMapKey(ancestor)
        return
    for ancestor in first.ancestors:
        for multikey in multimapkey_ancestors(rest):
            yield MultiMapKey(ancestor, *multikey.keys)

# XXX create a caching proxy to speed up things after registration is
# frozen
# create a freeze concept that kills registration, so that caching is safe
# freezing after software initialization is safe
# do we want to implement keys, values, etc? what do they mean?          
class MultiMap(object):
    """map that takes sequences of MapKey objects as key.

    A MultiMap is a map that takes sequences of MapKey objects as its
    key. We call such a sequence of MapKeys a MultiMapKey.

    When looking up a MultiMapKey in a MultiMap, it is compared
    component-wise to the MultiMapKeys registered in the MultiMap.
    Each of the components of a MultiMapKey found must be either equal
    to or a parent of the corresponding component of the MultiMapKey
    being looked up.  If more than one MultiMapKey could be found by a
    lookup, the one whose first component matches most specifically
    wins, the other components being considered as subordinate
    comparison criteria, in order.
    """
    def __init__(self):
        self._by_arity = {}
        
    def __setitem__(self, key, value):
        keys = list(key.keys)
        m = self._by_arity.get(key.arity)
        if m is None:
            if keys:
                self._by_arity[key.arity] = m = Map()
            else:
                self._by_arity[key.arity] = value
                return
        last_key = keys.pop()
    
        for k in keys:
            submap = m.exact_get(k)
            if submap is None:
                submap = m[k] = Map()
            m = submap
        m[last_key] = value

    def __getitem__(self, key):
        for multimapkey in key.ancestors:
            try:
                return self.exact_getitem(multimapkey)
            except KeyError:
                pass
        raise KeyError(key)
    
    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def exact_getitem(self, key):
        m = self._by_arity[key.arity]
        for k in key.keys:
            m = m.exact_getitem(k)
        return m

    def exact_get(self, key, default=None):
        try:
            return self.exact_getitem(key)
        except KeyError:
            return default
        
    def all(self, key):
        result = []
        for k in key.ancestors:
            try:
                result.append(self.exact_getitem(k))
            except KeyError:
                pass
        return result

class InverseMap(object):
    def __init__(self):
        self.d = {}
        self.ancestors = {}
        
    def __setitem__(self, key, value):
        self.d[key] = value
        for ancestor in key.ancestors:
            found = self.ancestors.get(ancestor)
            if found is not None and found in key.ancestors:
                continue
            self.ancestors[ancestor] = key
            
    def exact_getitem(self, key):
        return self.d[key]

    def exact_get(self, key, default=None):
        try:
            return self.exact_getitem(key)
        except KeyError:
            return default
        
    def __getitem__(self, key):
        return self.d[self.ancestors[key]]

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default
        
class ClassMapKey(object):
    def __init__(self, class_):
        self.key = class_
        self.parents = tuple(
            [ClassMapKey(base) for base in class_.__bases__])
        self.ancestors = [self] + [ClassMapKey(ancestor) for ancestor in
                          class_.__mro__[1:]]
        
    def __hash__(self):
        return hash(self.key)

    def __eq__(self, other):
        return self.key == other.key

    def __repr__(self):
        return "<ClassMapKey: %r>" % self.key

def ClassMultiMapKey(*classes):
    return MultiMapKey(*[ClassMapKey(class_) for class_ in classes])
