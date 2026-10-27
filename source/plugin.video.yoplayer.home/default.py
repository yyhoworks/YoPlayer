"""Dynamic home widget directory entry point."""
import os
import sys
from urllib.parse import parse_qs
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'resources', 'lib'))
from provider import directory

if __name__ == '__main__':
    arguments = parse_qs(sys.argv[2].lstrip('?'))
    directory(int(sys.argv[1]), arguments.get('route', ['libraries'])[0], arguments.get('q', [''])[0], arguments.get('revision', [''])[0], arguments.get('stream_type', [''])[0], arguments.get('probe', [''])[0] == '1')
