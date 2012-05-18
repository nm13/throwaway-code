#!/usr/bin/python

"""

    A threading-based "progress indicator" : something to be called, say, every second
    ( in a separate thread, of course) 
    
    Usage (plan): 
    
    #
    # << main thread : >>
    #
    
    # "the progress indicator"
    def print_progress( count, total ): ...
    
    # our object
    reporter = OurClass(print_progress, interval=1) # report every second 
    
    # something that should involve "progress report"
    def process(): 
       
        ...
        with reporter: # this opens a lock
            reporter.count = ... # same names as for function argument 
            reporter.total = ...
            
            reporter.start_once() # starts the thread on the first call, then does nothing  
    

"""

## from exceptions import Exception, TypeError, ValueError, RuntimeError
import exceptions
import inspect 

from types import FunctionType

# from locked import Locked
# from locked import _DbgRLock
import threading 

from time import sleep

import sys # stderr

## from collections import namedtuple # requires 2.6 or higher // *and is immutable !!*


## --------------------------------------------------------------------------  

#
# an RLock wrapper for debugging
#

class _DbgRLock :
    
    def __init__( self, name = None ):
        self._lock = threading.RLock(  )
        self.__name = name # dbg 
        
    def acquire( self ) :
        self._lock.acquire(  )
        print ">locked (%s)" % (self.__name, )

    def release( self ) :
        print "<unlocked (%s)" % ( self.__name,  )
        self._lock.release(  )


    def __enter__( self ) :
        self.acquire()
    
    def __exit__(self, type, value, traceback):
        self.release()
        # return False  


## --------------------------------------------------------------------------  

# from exceptions import Exception as base_exception

#
# our exceptions
#

class Error(exceptions.Exception): 
    """ Argument of wrong type or value, or a run-time error """

class TypeError( exceptions.TypeError, Error ): pass 
class ValueError( exceptions.ValueError, Error ): pass 
class RuntimeError( exceptions.RuntimeError, Error ): pass 


## --------------------------------------------------------------------------  

#
# check class attribute names for collisions with the function args : 
#

# code borrowed from the rlcompleter module ( renamed from 'get_class_members()' )
def _get_class_members(klass):
    """ useful for old-style classes; for new style classes, dir() seems to do the same as _uniq(_get_class_members()) """
    ret = dir(klass)
    if hasattr(klass,'__bases__'):
        for base in klass.__bases__:
            ret = ret + _get_class_members(base)
    return ret


def _uniq( seq ): 
    """ the 'set()' way (fallback to dict() when no 'set()') """
    return list(set(seq))


def _fieldnames( obj ):
    """ produces a list of all the attribute names for a given object; 
        due to a weird bug with isinstance() [isinstance(klass(), object) is True for *old-style* classes, sys.version: '2.6.5 (r265:79063, Apr 16 2010, 13:09:56) \n[GCC 4.4.3]'],
        
        we'll simplify our life to work only with class instances
    """
    
    klass = obj.__class__
    
    ret = None
    if issubclass( klass, object ) :
        
        ret = dir( obj ) # seems to work Ok for new-style classes
        
    else : # an old-style class instance 
        
        # code borrowed from the rlcompleter module ( see the code for Completer::attr_matches() )
        ret = dir( obj )
        ## if "__builtins__" in words:
        ##    ret.remove("__builtins__")

        if hasattr( obj, '__class__'):
            ret.append('__class__')
            ret.extend( _get_class_members(obj.__class__) )
            
            ret = _uniq( ret )
    
    # ret.sort()
    return ret


## --------------------------------------------------------------------------  

#
# a "mixin" to "forward" the internal '._lock' object's "context guard" interface
# ( the '__enter__' / '__exit__' stuff for the "with" construct )
#

## though it is easier to just inherit from RLock() -- this allows to "inherit" _part_ of the interface )
class _LockGuardMixin(object):
    
    def __enter__( self ):
        return self._lock.__enter__()
        
    # def __exit__( self, type, value, traceback ):
    def __exit__( self, *args ):
        return self._lock.__exit__( *args )
        
    

## --------------------------------------------------------------------------  

#
# we need a "named list": like "named tuple", but mutable )
#

# for "tuple protocol", see [ http://www.rafekettler.com/magicmethods.html ] 

## NamedList, then a descriptor to "forward" values 

class NamedList:
    """
        The list is intended to have a fixed length, 
        but the elements may change value 
        
        ( it is quite easy to implemend .append(), though )
    """
    
    def __init__( self, names, values = None, tail = False ):
        """ 'names' is assumed to be a sequence of names, 
            values may be either initial values or None ( == do not initialize the attributes ), 
            'tail' means that the values should be assigned to the last, not to the first names
        """
        
        # no for "name order"
        self.__no = {}
        
        #
        # check for reserved names -- and set the name order
        #
        
        _reserved = _fieldnames( self )
        for index, name in enumerate( names ) :  
            if name.startswith('__') or name in _reserved :
                return ValueError(  "the name '%s' is reserved; a name can not start with an '__' or be in the following list: %s" % (_reserved, )  )
            
            # else ...
            self.__no[ index ] = name
            ## # could be convenient
            ## self.__on[ name ] = index
        
        
        # an experiment have shown that we do not need to have a correct (even nonzero) value in .__len__(), but let's do things properly :     
        self.__len = index + 1
        
        
        #
        # initialize the attributes, if we have to
        #
        
        if values is not None :
            if tail: # assign values from the tail 
                names, values = [ list(s) for s in names, values ]
                for s in names, values:
                    s.reverse()
                
            for name, value in map(None, names, values) :
                if name is None: 
                    break
                # else ... 
                setattr(self, name, value)
                
            
    # this is all we need to have the "function( *args )" notation: 
    def __getitem__( self, index ):
        
        # if index not in self.__no.keys() : raise exceptions.IndexError( "index out of range: %d" % (index, )  ) 
        if index >= self.__len : raise exceptions.IndexError( "index out of range: %d" % (index, )  )
        
        attrname = self.__no[ index ]
        
        return getattr( self, attrname )

    ## # why need "setitem" if we have names ? )

    # seems we don't need this ( but let's have it )
    def __len__(self): return self.__len
    
    # we don't need this as well, but having an iterator seems to be convenient  
    def __iter__( self ): 
        
        # for i in sorted( self.__no.keys() ):
        for i in xrange( self.__len ) :
            
            attrname = self.__no[ i ]
            yield getattr( self, attrname )
            
        
    

## --------------------------------------------------------------------------  

#
# a "thread function" to run a periodic task 
#

## class PeriodicTask( threading.Thread )

"""

1. should call a given function periodically ;

2. should have 'locked' access to given arguments/attributes ;

3. should have a 'kill()' method

4. should sleep a given number of seconds

--- thread_func() : ---


with _lock:
    if ( _kill ): return
    
    _function( args )
    
sleep(_interval)



"""

class _CallPeriodically:
    """
        Provides a callable for a thread function,
        with a list of arguments and a .kill() method,
        both protected with a lock
    """
    
    def __init__( self, func, named_args, lock, interval=1 ):
        """
            with lock:
                __call__() func( *named_args )
                
            sleep( interval )
        
        """
    
        self.__func = func 
        self.__lock = lock
        self.__argref = named_args
        self.__interval = interval
        
        self.__done = False 
        
    def kill( self ): 
        """ set the internal 'stop' flag; should take the effect within "time(funk()) + interval" seconds """
        with self.__lock:
            self.__done = True
         
    
    def __call__( self ):
        
        while not self.__done: 
            
            with self.__lock:
                ## if self.__done: 
                ##     # delete the references ?
                ##     return
                    
                # else ...  
                try:
                    ## # dbg
                    ## sys.stderr.write('.')
                    self.__func( *(self.__argref) )
                except exceptions.Exception, e: # trying to handle most of them
                    print >>sys.stderr, "thread function caused an exception (will be ignored): '%s'" % (e, )
                
            sleep( self.__interval )
            
        # after thread exits, this may fail when finally gets active:
        ## # dbg
        ## with self.__lock:
        ##    print >>sys.stderr, "done."
        


## --------------------------------------------------------------------------  

''' # won't work, descriptors are designed for classes only !
    # ... 
    # well, we can create one class per attribute )) -- then use type() to create an anonymous class .. for one instance )) 
'''

#
# a descriptor to implement an attribute reference 
# # we plan to use it to access attributes in the NamedList 
# #
# # nb. an alternative would be to go with __getattr__ / __setattr__ < and __dir__ , see [ http://docs.python.org/library/functions.html#dir, http://bugs.python.org/issue1591665 ] > :
'''
def __setattr__(self, name, value):

    if name in self.__refs :
        setattr( self.__ref_obj, name, value )
    else:
        setattr( self, name, value )
        
# ... I guess we can inherit this ... 

# [ http://www.voidspace.org.uk/python/weblog/arch_d7_2011_05_21.shtml ]
def __dir__(self):
    return sorted(set((dir(type(self)) + list(self.__dict__) +
                  self._get_dynamic_attributes()))

'''
#

class _AttributeReference( object ): # not sure that the descriptors themselves should be new-style .. but let it be  
    
    def __init__( self, referred_obj, attrname ):
        
        self.__ref = referred_obj
        self.__name = attrname
        
    def _instance_check( self, instance ):
        
        if instance is None: 
            raise TypeError( "AttributeReference() descriptors are designed for instances, not classes [__get__( got None as the 2nd arg )]" ) 
    
    def __get__( self, instance, klass ): 
        
        # nb: do we really need this check ?
        self._instance_check( instance )
        
        return getattr( self.__ref, self.__name )
        
    def __set__( self, instance, value ): 
        
        # nb: do we really need this check ?
        self._instance_check( instance )

        return setattr( self.__ref, self.__name, value )
        
    # __delete__ is not supported at the moment
    # ( so that attribute deletion will delete the descriptor itself, I assume )

'''
    #
    # entering the attribute name twice is unthinkable ) 
    # 
    @staticmethod
    def set_attr_ref( klass, attrname, referred_obj ): 
        
        setattr( klass, attrname, AttributeReference(referred_obj, attrname) )
        

'''

#
# "one class per object": create a "mixin" to forward attribute access via multiple inheritance )
#

def _CreateParentMixin( referred_obj, attrnames, class_name = '--AttrRef--' ):
    
    #
    # todo: "--AtrrRef--" => "AtrrRef(ref_obj.__name__, < attr_names > )"
    #
    
    _dict_ = {}
    for name in attrnames:
        _dict_[ name ] = _AttributeReference( referred_obj, name )
        
    return type( class_name, (), _dict_ )
    

## --------------------------------------------------------------------------  

#
# implement the "do once" pattern
#

## can go the plain ol' way with a class, could also probably have used a decorator:
"""
Usage: 

def some_function(): ...

firsttime = HappensOnce()

if firsttime() : some_function()

--- an alternative form ---

call_once = CallOnce()

call_once(some_function, *args, **kwargs)

# the moral -- in our case the latter looks more clean )

"""

class CallOnce :  
    """ CallOnce()( func, *args, **kwargs ) calls the func() only once ) 
    
        nb. has to be thread-safe ("threading -- thread-safe")
    """  
    
    def __init__( self, lock = None ): 
        
        ## self.__lock = ( lock or threading.RLock() ) # unreadable )  
        self.__lock = threading.RLock() if ( lock is None ) else lock
        
        self.__done = False # the boolean flag / condition 
        
    def __call__( self, func, *args, **kwargs ): 
        """ on the first call, invokes the given function; on the next, does nothing; thread-safe """ 
        
        with self.__lock:
            
            ret = None
            if not self.__done : 
                ret = func( *args, **kwargs )
                self.__done = True
                
        return ret 
        
    

## --------------------------------------------------------------------------  

#
# "extra safety": wrap selected attribute access with RLock // -- won't work without an explicit deepcopy(), what may be too resource-consuming 
#


## --------------------------------------------------------------------------  

#
# get function argument names 
#

## inspect.getargspec( func ).args


## --------------------------------------------------------------------------  

'''
#
# a list of arguments, locked with an RLock
#

class _LockedArgs( object ):
    
    def __init__( self, argnames ):
        """
            argnames should be a sequence of argument names ; 
        """

        #
        # the argument names should not interfere
        #
        
        _reserved = _fieldnames(self)
        for argname in argnames :  
            if argname.startswith('__') or argname in _reserved :
                return ValueError(  "the function argument name '%s' is reserved; an argument name can not start with an '__' or be in the following list: %s" % (_reserved, )  )
'''

## --------------------------------------------------------------------------  

#
# may be we should just have used a class factory function and not bother with this __new__ fancy thing ) 
#

class Progress( object ) :
    
    """ calls a given function (with given args) periodically and in a separate thread ;
    
        There is a list of restrictions for the function argument:
        
        1) the function should be a Python _function_ (_not_ any callable -- 
          -- e.g. bound methods wouldn't raise an exception, but instance members access won't be protected ) ,
        2) it should not have any *varargs or **kwargs ( as they are harder to be Lock()-ed ),
        3) and its argument names should differ from any attribute names for this class.
           ( avoid names starting with underscores and use dir(<object>) for a quick check )
    """
    
    '''
    def _reserved(self, attrname):
        
        if attrname.startswith('__'): return True
        if attrname in _fieldnames( self ): return True
        # else ...
        return False
    '''
    
    # def _invalid_function( self, func, argspec = None ):
    @classmethod
    def _invalid_function( cls, func, argspec = None ): # can make this just an external function 
        """ returns the exception type or False ) """
        
        if type( func ) is not FunctionType: 
            return TypeError( "only Python functions (type '%s') are accepted [received function argument of type '%s']" % (FunctionType, type(func)) )
        
        # else ... 
        if argspec is None: argspec = inspect.getargspec( func ) 
        argnames, args, kwargs, defaults = argspec
        
        if  ( args is not None )  or  ( kwargs is not None )  :
            return ValueError(  "only Python functions with a fixed number of arguments are accepted [function argspec: '%s']" % ( argspec, )  )
       
        _reserved = _fieldnames( cls )
        for argname in argnames :  
            if argname.startswith('__') or argname in _reserved :
                return ValueError(  "the function argument name '%s' is reserved; an argument name can not start with an '__' or be in the following list: %s" % (_reserved, )  )
                
        # else  
        return False  
    
    @staticmethod
    def _new( cls, *args ):
        """ call the parent's __new__ (to be used as a stub) """
        return object.__new__( cls )

    def __new__( cls, func, sleep = 1, start_now = True, thread_name = None ): 
        """
            The initialization is a bit tricky: as we need to "forward" some attributes --
            -- and go with descriptors for that purpose ( an alternative would be to use __getattr__ / __setattr__ 
            and __dir__ ( search the above code for __dir__ ) ) ), 
            and as the descriptors could be set only at the class level -- 
            -- we have to create a per-object "mixin" class and "update" the object's parent class on the fly ;
            __new__ seems to be a convenient way to do this in a clean manner )
        """
        
        argspec = inspect.getargspec( func ) # .args
        
        # check args 
        e = cls._invalid_function( func, argspec  )
        if e: 
            raise e
            
        # else ... 
        argnames = argspec.args
        defaults = argspec.defaults
        named_list = NamedList( argnames, defaults, tail = True ) # assign default values from the tail, first left will get None
        
        ParentMixin = _CreateParentMixin( named_list, argnames )
        # Klass = type(cls.__name__ +  '~', (cls, ParentMixin), {}) # would be recursive 
        _dict_ = cls.__dict__.copy()
        # _dict_ = {}
        # _dict_['__new__'] = object.__new__
        # _dict_['__new__'] = lambda cls, *args: object.__new__(cls)
        _dict_['__new__'] = cls._new # don't complain about extra arguments 
        Klass = type( cls.__name__ +  '~', (_LockGuardMixin, ParentMixin, ), _dict_ )
        # Klass = type( cls.__name__ +  '~', (Progress, _LockGuardMixin, ParentMixin, ), _dict_ )
        
        self = Klass( func, sleep ) 
        
        #
        # we could have defined __init__() to set the rest 
        #
        
        self._lock = lock = threading.RLock()
        # self._lock = lock = _DbgRLock('dbglock')
        
        ## '__' magic should not be used probably
        ## self.__callable = thread_callable = _CallPeriodically(func, named_list, lock, sleep )
        self._callable = thread_callable = _CallPeriodically( func, named_list, lock, sleep )
        # keep a reference just in case ) 
        ## dbg
        self._thread = thread = threading.Thread( target = thread_callable, name = thread_name )
        thread.setDaemon( True )
        
        self._once = CallOnce()
        
        ## # dbg
        ## self._nl = named_list
        
        if start_now :
            # thread.start()
            self.__once( self.__thread.start ) 
        
        return self
        
    def _done( self ):
        """ tell the thread function to stop """
        
        self._callable.kill()
        
    def _start_once( self ):
        """ on the first call, starts the thread; then does nothing """
        
        self._once( self._thread.start ) 
        

    '''
    def __init__( self, func, sleep = 1 ):
        """ 
            
            an example: <to-do>
        """
    '''
        


## --------------------------------------------------------------------------  
## --------------------------------------------------------------------------  

# a test
if __name__ == '__main__' :
    
    ## pass
    import sys
    def func(a,b): print >>sys.stderr, "\tprogress: ", a,b

    N = 5

    p = Progress(func, start_now=False)
    p.a = 0
    p.b = N-1
    
    
    for i in xrange(N):
        
        with p:
            p.a = i
            
            p._start_once()
        
        # do hard work
        t = 2
        print >>sys.stderr, 'sleep %d seconds (i = %d)' % (t, i)
        sleep(t)
    
    p._done()
    
    sleep(1)