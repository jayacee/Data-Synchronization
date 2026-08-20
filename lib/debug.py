class debugger:
    def __init__(self,is_verbose=False):
        self.is_verbose = is_verbose
    def log_msg(self,msg):
        print(msg)
    def log_debug(self,debug_msg):
        if self.is_verbose:
            print(debug_msg)
