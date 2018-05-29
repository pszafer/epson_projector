"""
Test of epson.
"""

import epson_projector as epson
import logging

import sys
import time

root = logging.getLogger()
logging.getLogger('asyncio').setLevel(logging.DEBUG)
root.setLevel(logging.DEBUG)

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
root.addHandler(ch)



def _run(f):
    print("test")
    projector = epson.Projector('192.1684.131', port=80, encryption=False)

    resp = yield from projector.test('PWR')
    return resp
    # print(test)

obj = _run(3)
print(*obj, sep='\n')
# print(isOn)
