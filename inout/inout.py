#!/usr/bin/python

"""

    provides aliases for stdin and stdout:
    
    inout.infile == sys.stdin if sys.argv[] is empty,
    else it is file( sys.argv[1] ) ;
    
    inout.outfile is sys.stdout by default,
    but if there is sys.argv[2], 
    then outfile = file( sys.argv[2] ) .
    
    last but not least -- if sys.argv[1] == '-',
    then it means 'stdin' )

    usage:
    
        import inout
        inout.outfile.write( ... ) # stdout or file( sys.argv[2] )

    for convenience, there are two additional things:
    
    'infile_only' flag and a 'replace_extension()' function,
    usage:
    
        import inout
        # suppose the call was: <argv[0]> inputfile.ext
        
        if inout.infile_only:
            outfile = inout.replace_extension( 'new' ) # opens 'inputfile.new' for the output 

    On errors ( i.e. if we fail to open a file by the filename ), infile/outfile are set to None
    [ to help detect any arising problem ] ;  
    one can use code like
    
        if inout.infile is None:
            infile = sys.stdin
            
    explicitly, if he or she has such an intention .  

    Last but not least -- we rely on the system to close our files on exit,
    so, if worried, please do that explicitly -- e.g. by using a 'with' construct:
    
        with inout.outfile:
            # ... do some stuff ...  
            
    
    TODO: change the code to work only with arguments that do not start with an '-' !  
          # may be use the 'cmdopts' module for that matter 
"""

import sys
from exceptions import IndexError
from os.path import splitext

# a convenient alias
stderr = sys.stderr

input_name = None
output_name = None

infile_only = False

try:
    input_name = sys.argv[1]
    
    if input_name == '-':
        input_name = None
    
    output_name = sys.argv[2]
    
except IndexError:
    pass



def open_( *args, **kwargs ):
    """ returns None on errors """
    
    try:
        ret = open( *args, **kwargs )
    except:
        ret = None
        
    return ret


if input_name:
    infile = open_( input_name )
else:
    infile = sys.stdin

if output_name:
    outfile = open_( output_name, 'wb' )
else:
    outfile = sys.stdout
    
    if input_name:
        infile_only = True


# a useful helper 
def _replace_extension( filename, newext ):
    
    basename, ext = splitext( filename )
    result = '.'.join(  (basename, newext)  )
    
    return result


def replace_extension( newext, mode = 'wb' ):
    """ if there is an input file name, replace its extension to a given and try to open the resulting filename """
    
    newname = _replace_extension( infile_name, newext )
    
    _outfile = open( newname, mode )
    
    return _outfile

