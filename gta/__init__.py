import requests
import traceback
from io import BytesIO

from pbf.controller.PBF import PBF
from pbf.utils.RegCmd import RegCmd
from pbf.statement.XmlStatement import XmlStatement

_name = "GTA5"
_version = "1.0.0"
_description = "GTA5"
_author = "xzyStudio"
_cost = 0.00


def is_number(s):
    try:
        return int(s)
    except ValueError:
        pass
    return False


class gta(PBF):
    @RegCmd(
        name = " test",
        usage = "",
        permission = "owner",
        description = "test",
        mode = "test",
        hidden = 1
    )
    def test(self):
        self.client.msg(
            XmlStatement("""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<msg serviceID="1">
<item layout="4">
<title>testtitle</title>
</item>
</msg>""")
        ).send()

    @RegCmd(
        name="查询",
        usage="查询id",
        permission="anyone",
        description="查询rockstar id",
        mode="G  T  A  5"
    )
    def gta5RockStarID(self):
        try:
            self.client.msg().raw("正在处理...")
            from pbf.utils.pillow.build_image import BuildImage
            try:
                from paddleocr import PaddleOCR
            except ImportError:
                self.installPackage("paddleocr")
                from paddleocr import PaddleOCR

            captcha = "https://gta.julym.com/captcha.php?r=1134302707"
            send = "https://gta.julym.com/send.php?authcode={}&name={}".format("{}", self.data.message)
            s = requests.session()

            image = BuildImage.open(BytesIO(s.get(url=captcha).content))
            image = image.resize_canvas((image.width, image.height - 10), direction="north")
            image = image.resize((image.width + 10, image.height + 10), bg_color="#fff")
            data = image.save("png").getvalue()

            result = PaddleOCR(use_angle_cls=True, use_gpu=False).ocr(data, cls=True)
            str = result[0][-1][-1][0]
            # self.send(str)
            numList = []
            for i in str:
                if i == " " or i == "=":
                    continue
                num = is_number(i)
                if num != False:
                    numList.append(num)
            num = numList[0]
            for i in numList:
                if i == numList[0]:
                    continue
                if '×' in str or 'x' in str:
                    num *= i
                elif '+' in str:
                    num += i
                elif '-' in str:
                    num -= i
                elif '/' in str:
                    num /= i

            send = send.format(num)
            data = s.get(url=send).content.decode()
            self.client.msg().raw(data)
        except Exception as e:
            e = traceback.format_exc()
            self.client.msg().raw(e)
