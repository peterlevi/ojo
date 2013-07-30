import logging
import optparse

import gettext
from gettext import gettext as _
gettext.textdomain('ojo')

import ojo, ojoconfig

LEVELS = (logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG)

def main():
    version = ojoconfig.__version__
    # Support for command line options.
    usage = _("ojo [options]")
    parser = optparse.OptionParser(version="%%prog %s" % version, usage=usage)
    parser.add_option('-d', '--debug', dest='debug_mode', action='store_true',
        help=_('Print the maximum debugging info (implies -vv)'))
    parser.add_option('-v', '--verbose', dest='logging_level', action='count',
        help=_('set error_level output to warning, info, and then debug'))
    parser.set_defaults(logging_level=0)
    (options, args) = parser.parse_args()

    # set the verbosity
    if options.debug_mode:
        options.logging_level = 3
    logging.basicConfig(level=LEVELS[options.logging_level], format='%(asctime)s %(levelname)s %(message)s')

    # Run your cli application there.
    ojo.Ojo()

if __name__ == "__main__":
    main()
