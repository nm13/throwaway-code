
 For console-based programs mostly: a way to report progress 
 basing not on hte amount of work done, but periodically, 
 say, every second; obviously, we use a separate thread 
 to get this job done.

 Every module contains a little bit different in details
 implementation of the same; to "proxy" attributes, 
 the 'progress' module uses descriptors ( and some weird 
 '__new__' magic ), while 'progress2' uses old-style
 '__getattr__' / '__setattr__' approach.

