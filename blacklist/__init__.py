import time

from pbf.controller.PBF import PBF
from pbf.controller import Cache
from pbf.model.BlackListModel import BlackListModel
from pbf.model.BanWordsModel import BanWordsModel
from pbf.model import ModelBase
from pbf.utils.RegCmd import RegCmd
from pbf.statement.TextStatement import TextStatement
from pbf.statement.FaceStatement import FaceStatement

_name = "黑白系统"
_version = "1.0.1"
_description = "黑白系统，包括全局屏蔽、违禁词系统"
_author = "xzyStudio"
_cost = 0.00


class blacklist(PBF):
    @RegCmd(
        name="加违禁词 ",
        usage="加违禁词 <违禁词内容>",
        permission="anyone",
        description="添加违禁词",
        mode="违禁系统"
    )
    def addWeijin(self):
        uid = self.data.se.get('user_id')
        gid = self.data.se.get('group_id')
        message = self.data.args[1]

        if self.data.args[-1] == "单群":
            BanWordsModel()._insert(content=message, state=0, qn=gid, uuid=self.data.uuid)
        else:
            if uid == self.data.botSettings._get('owner'):
                BanWordsModel()._insert(content=message, state=0, qn=0, uuid=self.data.uuid)
            else:
                BanWordsModel()._insert(content=message, state=1, qn=0, uuid=self.data.uuid)
        self.client.msg(
            FaceStatement(54),
            TextStatement(' 插入成功，等待审核！')
        ).send()

    @RegCmd(
        name="违禁词垃圾箱",
        usage="违禁词垃圾箱",
        permission="owner",
        description="查看违禁词垃圾箱",
        mode="违禁系统"
    )
    def bWj(self):
        uid = self.data.se.get('user_id')
        gid = self.data.se.get('group_id')

        vKwList = BanWordsModel()._get(state=2)
        message = '[CQ:face,id=151] {0}-违禁词垃圾箱'.format(self.data.botSettings._get('name'))
        for i in vKwList:
            message += '\n[CQ:face,id=54] 违禁词：' + str(i.get('content')) + '\n      ID：' + str(i.get('id'))
        self.client.msg().raw(message)

    @RegCmd(
        name="违禁词审查列表",
        usage="违禁词审查列表",
        permission="owner",
        description="查看违禁词审核列表",
        mode="违禁系统"
    )
    def vWj(self):
        uid = self.data.se.get('user_id')
        gid = self.data.se.get('group_id')

        vKwList = BanWordsModel()._get(state=1)
        message = '[CQ:face,id=151] {0}-违禁词审核列表'.format(self.data.botSettings._get('name'))
        for i in vKwList:
            message += '\n[CQ:face,id=54] 违禁词：' + str(i.get('content')) + '\n      ID：' + str(i.get('id'))
        self.client.msg().raw(message)

    @RegCmd(
        name="违禁词删除列表",
        usage="违禁词删除列表",
        permission="owner",
        description="查看违禁词删除列表",
        mode="违禁系统"
    )
    def dvWj(self):
        uid = self.data.se.get('user_id')
        gid = self.data.se.get('group_id')

        vKwList = BanWordsModel()._get(state=3)
        message = '[CQ:face,id=151] {0}-违禁词删除列表'.format(self.data.botSettings._get('name'))
        for i in vKwList:
            message += '\n[CQ:face,id=54] 违禁词：' + str(i.get('content')) + '\n      ID：' + str(i.get('id'))
        self.client.msg().raw(message)

    @RegCmd(
        name="违禁词审查 ",
        usage="违禁词审查 <ID> <是否通过>",
        permission="owner",
        description="审核违禁词",
        mode="违禁系统"
    )
    def tWj(self):
        uid = self.data.se.get('user_id')
        gid = self.data.se.get('group_id')
        message = self.data.message

        message1 = message.split(' ')
        kwid = message1[0]
        iff = message1[1]
        if iff == '通过':
            state = 0
            message = '[CQ:face,id=54] 已通过！'
        else:
            state = 2
            message = '[CQ:face,id=54] 已移至回收站！'
        BanWordsModel()._set({"id":kwid}, state=state)

        self.client.msg().raw(message)

    @RegCmd(
        name="删违禁词 ",
        usage="删违禁词 <违禁词内容>",
        permission="anyone",
        description="删除指定的违禁词",
        mode="违禁系统"
    )
    def delWeijin(self):
        uid = self.data.se.get('user_id')
        gid = self.data.se.get('group_id')
        message = self.data.message

        if uid == self.data.botSettings._get('owner'):
            BanWordsModel()._set({"content":message, "qn":0}, state=2)
        else:
            BanWordsModel()._set({"content":message, "qn":0}, state=3)

        self.client.msg().raw('[CQ:face,id=54] 已提交申请，等待审核！')

    @RegCmd(
        name="删群违禁词 ",
        usage="删群违禁词 <违禁词内容>",
        permission="ao",
        description="删除指定的群聊违禁词",
        mode="违禁系统"
    )
    def delQunWeijin(self):
        uid = self.data.se.get('user_id')
        gid = self.data.se.get('group_id')
        message = self.data.message

        BanWordsModel()._delete(content=message)

        self.client.msg().raw('[CQ:face,id=54] 已删除！')

    @RegCmd(
        name="全局屏蔽列表",
        usage="全局屏蔽列表",
        permission="anyone",
        description="列出被全局屏蔽的人",
        mode="全局屏蔽"
    )
    def listQuanjing(self):
        uid = self.data.se.get('user_id')
        gid = self.data.se.get('group_id')

        message = '[CQ:face,id=189] {0}-全局拉黑列表'.format(self.data.botSettings._get('name'))
        modelBase = ModelBase()
        modelBase.db_table = 'black_list'
        quanjing = Cache.get(modelBase._c())
        for j in quanjing:
            items = quanjing.get(j)
            for l in items:
                i = items.get(l)
                message += '\n[CQ:face,id=54] 用户：' + str(i.get('qn')) + '\n     原因：' + str(i.get('reason'))
        self.client.msg().raw(message)

    @RegCmd(
        name="删全局屏蔽 ",
        usage="删全局屏蔽 <要删的qq号>",
        permission="ro",
        description="删除某个被全局屏蔽的人",
        mode="全局屏蔽"
    )
    def deleteQuanjing(self):
        uid = self.data.se.get('user_id')
        gid = self.data.se.get('group_id')
        message = self.data.message

        BlackListModel(uuid=self.data.uuid, qn=int(message))._delete()

        self.client.msg().raw('[CQ:face,id=54] 删除成功！')

    @RegCmd(
        name="加全局屏蔽 ",
        usage="加全局屏蔽 <要加的qq号> <原因>",
        permission="owner",
        description="添加某个被全局屏蔽的人",
        mode="全局屏蔽"
    )
    def addQuanjing(self):
        uid = self.data.se.get('user_id')
        gid = self.data.se.get('group_id')
        message = self.data.message

        message1 = message.split(' ')
        qn = message1[0]
        reason = message1[1]
        BlackListModel(uuid=self.data.uuid, time=time.time(), reason=reason, qn=qn)

        self.client.msg().raw('[CQ:face,id=54] 添加成功！')