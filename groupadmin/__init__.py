import requests, time
from pbf.controller import Cache
from pbf.controller.PBF import PBF
from pbf.utils.RegCmd import RegCmd
from pbf.utils.CQCode import CQCode
from pbf.model.SettingNameModel import SettingNameModel

_name = "群聊管理"
_version = "1.0.1"
_description = "轻松管理群聊"
_author = "xzyStudio"
_cost = 0.00

class groupadmin(PBF):
    @RegCmd(
        name = "解全员禁言",
        usage = "解全员禁言",
        permission = "admin",
        description = "解全体禁言",
        mode = "群聊管理"
    )
    def unmuteall(self):
        self.muteall(mode=0)
    
    @RegCmd(
        name = "删除好友 ",
        usage = "删除好友 <QQ号>",
        permission = "owner",
        description = "让机器人删除好友",
        mode = "防护系统"
    )
    def delete_friend(self):
        dataa = self.client.CallApi('delete_friend', {"friend_id":self.data.message})
    
    def delete_msg(self):
        datajson = self.client.CallApi('delete_msg', {'message_id':self.data.se.get('message_id')})
        return 200 if datajson['status'] == 'ok' else 500
    
    @RegCmd(
        name = "发送公告 ",
        usage = "发送公告 <公告内容>",
        permission = "ao",
        description = "发送公告",
        mode = "群聊管理"
    )
    def sendnotice(self):
        gid = self.data.se.get('group_id')
        message = self.data.message
        
        dataa = self.client.CallApi('_send_group_notice', {"group_id":gid,"content":message})
        if dataa['status'] == 'ok':
            self.client.msg().raw('[CQ:face,id=54] 成功！')
        else:
            self.client.msg().raw('[CQ:face,id=151] 发送公告失败')
    
    @RegCmd(
        name = "全员禁言",
        usage = "全员禁言",
        permission = "admin",
        description = "全体禁言",
        mode = "群聊管理"
    )
    def muteall(self, iff=1, mode=1):
        gid = self.data.se.get('group_id')
        
        dataa = self.client.CallApi('set_group_whole_ban', {"group_id":gid,"enable":mode})
        message = '[CQ:face,id=54] 执行成功！' if dataa['status'] == 'ok' else '[CQ:face,id=151] 执行失败！'
        if iff:
            self.client.msg().raw(message)
    
    @RegCmd(
        name = "mute ",
        usage = "mute <@要禁言的人> <禁言时长（秒）>",
        permission = "ao",
        description = "禁言某人",
        mode = "群聊管理"
    )
    def mute(self):
        uid = self.data.se.get('user_id')
        gid = self.data.se.get('group_id')
        message = self.data.message
        
        message1 = message.split()
        duration = message1[1] or 60
        
        userid = CQCode(message1[0]).get("qq")[0]
        dataa = self.client.CallApi('set_group_ban', {"group_id":gid,"user_id":userid,"duration":duration})
        
        if dataa['status'] == 'ok':
            self.client.msg().raw('[CQ:face,id=54] 执行成功！')
        else:
            self.client.msg().raw('[CQ:face,id=151] 执行失败！\n原因：{}\n执行的群：{}\nface54可能为GOCQ的bug，请提交issue！'.format(dataa['wording'], gid))
    
    @RegCmd(
        name = "kick ",
        usage = "kick <@要踢的人>",
        permission = "ao",
        description = "踢出某人",
        mode = "群聊管理"
    )
    def kick(self):
        uid = self.data.se.get('user_id')
        gid = self.data.se.get('group_id')
        message = CQCode(self.data.message).get("qq")[0]
        
        dataa = self.client.CallApi('set_group_kick', {"group_id":gid,"user_id":message})
        if dataa['status'] == 'ok':
            self.client.msg().raw('[CQ:face,id=54] 执行成功！')
        else:
            self.client.msg().raw('[CQ:face,id=151] 执行失败！')

    @RegCmd(
        name = "修改设置",
        usage = "修改设置",
        permission = "ao",
        description = "设置机器人设定的值",
        mode = "群聊管理"
    )
    def setSettings(self):
        gid = self.data.se.get('group_id')
        message = self.data.message
        
        ob = self.commandListener.get()
        model = SettingNameModel()
        if ob == 404:
            self.client.msg().raw('开始修改群聊设置，在此期间，您可以随时发送"退出"来退出。')
            message = "设置项目列表："
            for i in model._getAll():
                message += "\n{}. {}".format(i.get("id"), i.get("name"))
            self.client.msg().raw(message)
            self.client.msg().raw("请发送要修改的项的序号")
            self.commandListener.set('groupadmin@setSettings', {'key':''})
            return True
        
        step = int(ob.get('step'))
        args = ob.get('args')
        
        if step == 1:
            settings = self.data.groupSettings
            data = model._get(id=message)[0]
            self.commandListener.set(args={'key':data.get("description")})
            message = '[CQ:face,id=54] '+str(data.get('name'))+'：'+str(data.get('description'))+'\n     当前的值：'+str(settings._get(data.get('description')))
            if data.get('other') != '':
                message += '\n     描述：'+str(data.get('other'))
            self.client.msg().raw(message)
            self.client.msg().raw('请发送要修改成的值\n如果修改为空请发送"None"（不包含引号）\n如果是开关类的，则1为开 0为关')
        
        if step == 2:
            if message == "None":
                message = None
            key = args.get('key')
            self.commandListener.remove()
            self.data.groupSettings._set(**{key: message})
            
            self.client.msg().raw("修改成功！")


"""
[2023-08-07 14:15:39] [BOT] [123456789/2417481092/871260826] [ERROR] Traceback (most recent call last):
  File "/www/gch/v4/pbf/controller/PBF.py", line 89, in execPlugin
    return getattr(instance, methodName)()
  File "/www/gch/v4/pbf/utils/RegCmd.py", line 31, in wrapper
    return func(*args, **kwargs)
  File "/www/gch/v4/test/plugins/groupadmin/__init__.py", line 153, in setSettings
    model._set({"uuid":self.data.uuid, "qn":gid}, **{key: message})
  File "/www/gch/v4/pbf/model/__init__.py", line 382, in _set
    if i.get(k) != type(i.get(k))(v):
TypeError: NoneType takes no arguments
"""