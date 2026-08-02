import unittest
from pccooler_lcd.protocol_cp3 import frame,announce_frame,complete_frame,parse_png_dimensions

class ProtocolTests(unittest.TestCase):
    def test_known_announce(self):
        expected=(b"\x5a\x00\xa9POST transport 1\r\nSeqNumber=452\r\nDate=1785655099284\r\nContentType=json\r\nContentLength=73\r\n\r\n"
                  b'{"type":"media","fileSize":8297,"fileName":"2026-08-02_02-18-19-283.osd"}\x6d\x5a')
        actual=announce_frame(452,1785655099284,"2026-08-02_02-18-19-283.osd",8297)
        self.assertEqual(actual,expected)

    def test_known_complete(self):
        expected=(b"\x5a\x00\x99POST transported 1\r\nSeqNumber=453\r\nDate=1785655099306\r\nContentType=json\r\nContentLength=55\r\n\r\n"
                  b'{"md5":"todo","fileName":"2026-08-02_02-18-19-283.osd"}\x5d\x5a')
        actual=complete_frame(453,1785655099306,"2026-08-02_02-18-19-283.osd")
        self.assertEqual(actual,expected)

    def test_frame_length(self):
        f=frame(b"abc")
        self.assertEqual(len(f),8)
        self.assertEqual(int.from_bytes(f[1:3],"big"),8)

    def test_png_dimensions(self):
        data=b"\x89PNG\r\n\x1a\n"+b"\x00\x00\x00\x0dIHDR"+bytes.fromhex("00000140000000f0")
        self.assertEqual(parse_png_dimensions(data),(320,240))

if __name__=="__main__": unittest.main()
