from ipopen import IPopen


class NodeRepl(IPopen):

    def __init__(self):
        super(NodeRepl, self).__init__(["node", "-i"], prompt=('> ', '... '))
