#!/usr/bin/python

"""

    A threading-based "progress indicator" : something to be called, say, every second
    ( in a separate thread, of course) 
    
    #
    # "old-style" implementation: __getattr__ / __setattr__ instead of these fancy __new__ / desciptor stuff
    #
    
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

class AttributeError( exceptions.AttributeError, Error ): pass 


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
## class _LockGuardMixin(object):
class _LockGuardMixin:
    
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
        ## setattr( self, name, value )
        # [ http://docs.python.org/release/2.5.2/ref/attribute-access.html ] :  
        object.__setattr__( self, name, value ) or self.__dict__[ name ] = value
        
# ... I guess we can inherit this ... 

# [ http://www.voidspace.org.uk/python/weblog/arch_d7_2011_05_21.shtml ]
def __dir__(self):
    return sorted(set((dir(type(self)) + list(self.__dict__) +
                  self._get_dynamic_attributes()))

'''

class _ForwardAttributesMixin:
    """"""
    
    def __init__( self, referred_obj, attr_names ):
        """ 'attr_names' is a sequence of strings; use 'a b c'.split() , if it saves typing )  """ 
        
        ## # dbg
        ## print "__init__: started"
        
        self.__ref = referred_obj
        self.__names = attr_names[:]

        ## # dbg
        ## print "__init__: done"

    def __getattr__( self, attrname ):
        
        ## # dbg:
        ## # print "__getattr__(%s, %s)" % (self, attrname) # inf. recursion in __str__ !!
        ## print "__getattr__(%s)" % ( attrname, )
        
        # if getattr( self, '__ref' ) # this won't mangle ! ( + would fall into recursion ) )
        '''
        try:
            self.__ref # did __init__ already happen ?  
            self.__names # for a complete check  
        except exceptions.AttributeError:
            pass # no, it didn't
        else: # probably it did )
        '''
        
        # if self.__dict__.get( '_ForwardAttributesMixin' + '__ref', None ) is not None: 
        if self.__dict__.get( '_ForwardAttributesMixin__ref', None ) is not None: 
            
            if attrname in self.__names:
                return getattr( self.__ref, attrname )
            # else ...  
            # we are in __getattr__ -- this means that the "normal" attributes 
            # have already been looked for 
            raise AttributeError(  "failed to get an attribute '%s' for class %s"  %  ( attrname, self.__class__ )  )     


    def __dir( self ):
        """ as we're going to define __dir__(), we need a way to get local dictionary """
        
        big_list = dir( self.__class__ ) # can not use _fieldnames() : would be recursive ! )
        # big_list.extend( list( self.__dict__ ) ) # list( dict ) == list( dict.keys() )
        big_list.extend( self.__dict__.keys() )  
        
        return sorted( _uniq( big_list ) )


    def __setattr__( self, attrname, value ): 
        
        ## # dbg:
        ## # print "__setattr__(%s, %s)" % (self, attrname) # inf. recursion in __str__ !!
        ## print "__setattr__(%s)" % ( attrname, )
        
        set_local = True # 'normal' attributes have the priority 
        
        # names = getattr( self, '_ForwardAttributesMixin__names', () ) # in __init__() returns None anyway (?!)
        names = self.__dict__.get( '_ForwardAttributesMixin__names', () )
        ## # dbg:
        ## print "got __names:", names
        
        if attrname not in self.__dir() and attrname in names : 
            set_local = False
            
        if set_local : # the "normal" way  
            # [ http://docs.python.org/release/2.5.2/ref/attribute-access.html ] # use object.__setattr__ or __dict__  
            # [ http://bugs.python.org/issue14671 ] # make the difference 
            # [  ]
            new_style = issubclass( self.__class__, object )
            if new_style :  
                # return super(_ForwardAttributesMixin, self).__setattr__(  ) 
                # let's try to avoid an extra proxy object creation
                return object.__setattr__( self, attrname, value )
            else: # an old-style class instance 
                # to-do: check for the attrname in parents ? ( for rare cases like a "singleton" class attribute ? )
                self.__dict__[ attrname ] = value
                return value # allow "a =b=c" expressions )
                
        else: 
            return setattr( self.__ref, attrname, value )

    '''
    def __dir__( self ) :
        """  see [ http://www.voidspace.org.uk/python/weblog/arch_d7_2011_05_21.shtml ]  """
        
        big_list = dir( self.__class__ ) # can not use _fieldnames() : would be recursive ! )
        # big_list.extend( list( self.__dict__ ) ) # list( dict ) == list( dict.keys() )
        big_list.extend( self.__dict__.keys() )  
        
        big_list.extend( self._fw_names )
        
        return sorted( _uniq( big_list ) )
    '''

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

# dbg
def _dump(self):
    print dir(self)
    print _fieldnames(self)
    sys.exit()

class Progress( _ForwardAttributesMixin, _LockGuardMixin ) :
    
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
    def _invalid_function( self, func, argspec = None ): # can make this just an external function 
        """ returns the exception type or False ) """
        
        if type( func ) is not FunctionType: 
            return TypeError( "only Python functions (type '%s') are accepted [received function argument of type '%s']" % (FunctionType, type(func)) )
        
        # else ... 
        if argspec is None: argspec = inspect.getargspec( func ) 
        argnames, args, kwargs, defaults = argspec
        
        if  ( args is not None )  or  ( kwargs is not None )  :
            return ValueError(  "only Python functions with a fixed number of arguments are accepted [function argspec: '%s']" % ( argspec, )  )
       
        _reserved = _fieldnames( self )
        for argname in argnames :  
            if argname.startswith('__') or argname in _reserved :
                return ValueError(  "the function argument name '%s' is reserved; an argument name can not start with an '__' or be in the following list: %s" % (_reserved, )  )
                
        # else  
        return False  
    

    def __init__( self, func, sleep = 1, start_now = True, thread_name = None ): 
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
        e = self._invalid_function( func, argspec  )
        if e: 
            raise e
            
        # else ... ( most '__'-fields are used for debugging mostly ) )
        ## self.__argnames = argnames = argspec.args
        argnames = argspec.args
        defaults = argspec.defaults
        ## self.__nl = named_list = NamedList( argnames, defaults, tail = True ) # assign default values from the tail, first left will get None
        named_list = NamedList( argnames, defaults, tail = True ) # assign default values from the tail, first left will get None
                
        _ForwardAttributesMixin.__init__( self, named_list, argnames )
                
        self._lock = lock = threading.RLock()
        # self._lock = lock = _DbgRLock('dbglock') # also serves as a _LockGuardMixin "__init__" )
        
        self.__callable = thread_callable = _CallPeriodically(func, named_list, lock, sleep )
        # keep a reference just in case ) 
        self.__thread = thread = threading.Thread( target = thread_callable, name = thread_name )
        thread.setDaemon( True )
        
        self.__once = CallOnce()
        
        if start_now :
            # thread.start()
            self.__once( self.__thread.start ) 
            
        
        
    def _done( self ):
        """ tell the thread function to stop """
        
        self.__callable.kill()
        
    def _start_once( self ):
        """ on the first call, starts the thread; then does nothing """
        
        self.__once( self.__thread.start ) 
        

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
    
    ## # dbg
    ## sys.stdout = sys.stderr
    
    N = 5

    import sys
    def func( a=0, b=N-1 ): print >>sys.stderr, "\tprogress: ", a,b

    # p = Progress(func, start_now=False)
    # or start immediately:
    p = Progress( func )
    ## # or set the values manually
    ## p.a = 0
    ## p.b = N-1
    
    for i in xrange(N):
        
        with p:
            p.a = i
            
            # p._start_once() # do not need that if we start immediately 
        
        # do hard work
        t = 2
        print >>sys.stderr, 'sleep %d seconds (i = %d)' % (t, i)
        sleep(t)
    
    p._done()
    
    sleep(1)
    
