from deploy import set_weight
if __name__ == '__main__':
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option('-m', '--machine', dest = 'machine', type=str, default = None)
    parser.add_option('-w', '--weight', dest = 'weight', type=int, default = None)  
    opts, args = parser.parse_args()
    assert opts.weight is not None
    assert opts.machine
    set_weight(opts.machine, opts.weight)