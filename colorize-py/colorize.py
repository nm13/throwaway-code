#!/usr/bin/python

"""Python Source HTML Colorizer (customized from MoinMoin by David Mertz and then slightly edited ))"""

# Imports
import cgi, string, sys, cStringIO
import keyword, token, tokenize

_KEYWORD = token.NT_OFFSET + 1
_TEXT    = token.NT_OFFSET + 2

_colors = {
    token.NUMBER:       'black',
    token.OP:            None,
    token.STRING:       'brown',
    tokenize.COMMENT:   'green',
    token.NAME:          None,
    token.ERRORTOKEN:   'red',
    _KEYWORD:           'blue',
    _TEXT:              'black',
}

_fontsize = 1.2 # "*100%"
_fontsize_str = str(  int( _fontsize * 100 )  ) + '%' # 1.1 => '110%'

class Parser:
    """ Colorize python source"""
    
    def __init__( self, raw, output = sys.stdout, color_mapping = _colors ):
        """ Store the source text"""
        
        self._colors = color_mapping
        self._outfile = output
        
        self._raw = string.strip(string.expandtabs(raw))
        

    def output(self):
        """ Parse and send the colored source."""
        
        # store line offsets in self.lines
        self.lines = [0, 0]
        pos = 0
        while 1:
            pos = string.find(self._raw, '\n', pos) + 1
            if not pos: break
            self.lines.append(pos)
        self.lines.append(len(self._raw))

        # parse the source and write it
        self.pos = 0
        text = cStringIO.StringIO(self._raw)
        try:
            tokenize.tokenize(text.readline, self) # uses self.__call__() 
        except tokenize.TokenError, ex:
            msg = ex[0]
            line = ex[1][0]
            print "ERROR: %s %s" % (msg, self._raw[self.lines[line]:])

    def __call__(self, toktype, toktext, (srow,scol), (erow,ecol), line):
        """ Token handler"""
        # calculate new positions
        oldpos = self.pos
        newpos = self.lines[srow] + scol
        self.pos = newpos + len(toktext)

        # handle newlines
        if toktype in [token.NEWLINE, tokenize.NL]:
            self._outfile.write('\n')
            return

        # send the original whitespace, if needed
        if newpos > oldpos:
            self._outfile.write(self._raw[oldpos:newpos])

        # skip indenting tokens
        if toktype in [token.INDENT, token.DEDENT]:
            self.pos = newpos
            return

        # map token type to a color group
        if token.LPAR <= toktype and toktype <= token.OP:
            toktype = token.OP
        elif toktype == token.NAME and keyword.iskeyword(toktext):
            toktype = _KEYWORD
        color = self._colors.get(toktype, self._colors[_TEXT])

        # send text
        toktext = cgi.escape(toktext)
        if not color:
            if toktext: self._outfile.write(toktext)
        elif color == 'black':
            if toktext: self._outfile.write('<b>%s</b>' % (toktext))

        else: # [ http://www.w3schools.com/tags/att_font_color.asp ]
            if toktext: self._outfile.write('<b style="color:%s">%s</b>'
                                         % (color, toktext))

if __name__ == "__main__":
    import sys
    
    infile = sys.stdin
    outfile = sys.stdout

    try:
        input_file_name = sys.argv[1] 
        infile = open( input_file_name, 'rb' )
        print >>sys.stderr, "taking INPUT from the file %s" % ( input_file_name, ) 
        
        
        output_file_name = sys.argv[2] 
        outfile = open( output_file_name, 'wt' )
        print >>sys.stderr, "saving OUTPUT to the file %s" % ( output_file_name, ) 
        
    except:
        pass
    
    ## # hackHACK
    ## self._outfile=outfile
    
    print >>outfile, '<pre style="font-size:%s">' % (_fontsize_str, )    
    Parser(infile.read(), outfile).output()
    print >>outfile, '</pre>'

    infile.close()
    outfile.close()
