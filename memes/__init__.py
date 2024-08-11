import time

from pbf.controller.PBF import PBF
from pbf.utils.RegCmd import RegCmd
from pbf.model.MemesModel import MemesModel

_name = "表情包增强"
_version = "1.0.1"
_description = "增强qq的表情包功能"
_author = "xzyStudio"
_cost = 0.00


class memes(PBF):
    @RegCmd(
        name="添加快捷表情 ",
        usage="添加快捷表情 <触发关键词> <图片>",
        permission="anyone",
        description="添加快捷表情",
        mode="表情增强"
    )
    def add(self):
        if '\r\n' in self.data.args[2]:
            self.data.args[2] = self.data.args[2].replace("\r\n", "")
        MemesModel()._insert(keyword=self.data.args[1], url=self.data.args[2], uid=self.data.se.get("user_id"), time=time.time())
        self.client.msg().raw("face54已添加！")

    @RegCmd(
        name="MemesMessageListener",
        usage="MessageListener",
        permission="anyone",
        description="MessageListener",
        mode="表情增强",
        type="message"
    )
    def messageListener(self):
        memesList = MemesModel()._get(uid=self.data.se.get("user_id"))
        for i in memesList:
            if self.regex.pair(i.get("keyword"), self.data.message):
                self.client.msg().raw(i.get("url"))
                # self.client.CallApi('delete_msg', {'message_id': self.data.se.get('message_id')})
                return

    @RegCmd(
        name="快捷表情列表",
        usage="快捷表情列表",
        permission="anyone",
        description="列出您的快捷表情",
        mode="表情增强"
    )
    def listMemes(self):
        arr = []
        memesList = MemesModel()._get(uid=self.data.se.get("user_id"))
        for i in memesList:
            arr.append({"type": "node", "data": {"name": self.data.botSettings._get("name"),
                                                 "uin": self.data.botSettings._get("myselfqn"),
                                                 "content": "{} => {}".format(i.get("keyword"), i.get("url"))}})
        self.client.CallApi("send_group_forward_msg", {"group_id": self.data.se.get("group_id"), "messages": arr})

    @RegCmd(
        name="删除快捷表情 ",
        usage="删除快捷表情 <关键词>",
        permission="anyone",
        description="删除快捷表情",
        mode="表情增强"
    )
    def rmMemes(self):
        MemesModel()._delete(keyword=self.data.message, uid=self.data.se.get("user_id"))
        self.client.msg().raw("face54已删除！")
