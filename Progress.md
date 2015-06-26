Wrote this to familiarize myself with the Python `threading` module, as well as with the descriptor concept and some new fancy stuff like `__new__`.

Usage example:
```

# from progress import *

N = 5 # let's say there's a progress counter that goes from 1 to 5

def func( a=1, b=N ):
""" this is our progress indicator """
print "\tprogress: ", a,b

# this creates (and starts) our thread object;
p = Progress( func, sleep=1 ) # sleep interval between reports is one second (the default)

for i in xrange(N): # let 'i' be the measure of our progress

with p: # this opens a lock
p.a = i+1 # field names are created after the function parameters
# and take the default values for initialization

# pretend we do hard work here: sleep for two seconds
t = 2
print >>sys.stderr, 'sleep %d seconds (i = %d)' % (t, i)
sleep(t)

# this stops the reporter; as it runs in so called 'daemon mode' (Python term, not Unix term),
# this method need not be called to prevent the main thread from exiting ;
# call it only if there are other things to do now
# p._done()

```

For more, see the module's docstring and the testing code in the `"if __name__ == '__main__'"` branch.

NB. There is also a version (`progress2`) that is old-style and uses only `__setattr__` / `__getattr__` instead of descriptors.

