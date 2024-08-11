import json
import random
import re
import requests
import traceback
import urllib

try:
    import websocket
except ImportError:
    import pip

    pip.main(['install', "websocket-client"])
    import websocket
from pbf.controller.PBF import PBF
from pbf.statement.FaceStatement import FaceStatement
from pbf.statement.TextStatement import TextStatement
from pbf.statement import Statement
from pbf.statement.ImageStatement import ImageStatement
from pbf.model.MCCmdModel import MCCmdModel
from pbf.utils.RegCmd import RegCmd

_name = "MC服务器"
_version = "1.0.1"
_description = "在QQ群内轻松管理MC服务器"
_author = "xzyStudio"
_cost = 0.00


class mcserver(PBF):
    def CheckAndGetSettings(self):
        setting = self.data.groupSettings
        if setting._get('MCSMApi') and setting._get('MCSMUuid') and setting._get('MCSMKey') and setting._get('MCSMRemote'):
            return setting
        else:
            return 404

    def CheckAndGetSettingsSocket(self):
        setting = self.data.groupSettings
        if len(setting._get("client_id").strip()) != 0 and len(setting._get("client_secret").strip()) != 0:
            return setting
        else:
            return 404

    def sendSocket(self, type, data, iff=True):
        setting = self.CheckAndGetSettingsSocket()
        if setting == 404:
            return False
        client_id = setting._get("client_id")
        client_secret = setting._get("client_secret")
        self.logger.debug(data)
        params = {
            "type": type,
            "data": data,
            "client_id": client_id,
            "client_secret": client_secret,
            "flag": "flag"
        }
        ws = websocket.WebSocket()
        ws.connect("wss://socket.xzynb.top/ws")
        ws.send(json.dumps(params))
        ws.close()
        if iff:
            self.client.msg().raw("face54 命令已发送！")

    def hum_convert(self, value):
        units = ["B", "KB", "MB", "GB", "TB", "PB"]
        size = 1024.0
        for i in range(len(units)):
            if (value / size) < 1:
                return "%.2f%s" % (value, units[i])
            value = value / size

    @RegCmd(
        name="服务器状态",
        usage="服务器状态",
        permission="anyone",
        description="服务器状态",
        mode="MC服务器"
    )
    def state(self):
        uid = self.data.se.get('user_id')
        gid = self.data.se.get('group_id')
        setting = self.CheckAndGetSettings()
        if setting == 404:
            self.client.msg().raw('请先绑定服务器！\n绑定教程见作者B站：xzystudio1')
            return

        statusList = ["状态未知", "已停止", "正在停止", "正在启动", "正在运行"]

        dataa = requests.get(url='{0}/api/instance?uuid={1}&remote_uuid={2}&apikey={3}'.format(setting._get('MCSMApi'),
                                                                                               setting._get('MCSMUuid'),
                                                                                               setting._get(
                                                                                                   'MCSMRemote'),
                                                                                               setting._get('MCSMKey')))
        datajson = dataa.json()

        if datajson['status'] == 200:
            data = '[CQ:face,id=54] 实例ID：' + datajson['data']['instanceUuid'] + '\n[CQ:face,id=54] 当前状态：' + \
                   statusList[datajson['data']['status'] + 1] + '\n[CQ:face,id=54] 服务器名称：' + str(
                datajson['data']['config']['nickname']) + '\n[CQ:face,id=54] 服务器类型：' + str(
                datajson['data']['config']['type']) + '\n[CQ:face,id=54] 在线人数：' + str(
                datajson['data']['info']['currentPlayers']) + '\n[CQ:face,id=54] 最大人数：' + str(
                datajson['data']['info']['maxPlayers'])
        else:
            data = '[CQ:face,id=151] 执行失败！\n原因：' + datajson.get('data')
        self.client.msg().raw(data)

    @RegCmd(
        name="关闭服务器",
        usage="关闭服务器",
        permission="ao",
        description="关闭服务器",
        mode="MC服务器"
    )
    def stop(self):
        uid = self.data.se.get('user_id')
        gid = self.data.se.get('group_id')
        setting = self.CheckAndGetSettings()
        if setting == 404:
            setting = self.CheckAndGetSettingsSocket()
            if setting == 404:
                self.client.msg().raw('请先绑定服务器！\n绑定教程见作者B站：xzystudio1')
                return

            self.sendSocket("command", {"cmd": "stop"})
            return

        dataa = requests.get(
            url='{0}/api/protected_instance/stop?uuid={1}&remote_uuid={2}&apikey={3}'.format(setting._get('MCSMApi'),
                                                                                             setting._get('MCSMUuid'),
                                                                                             setting._get('MCSMRemote'),
                                                                                             setting._get('MCSMKey')))
        datajson = dataa.json()
        if datajson['status'] == 200:
            data = '[CQ:face,id=54] 执行成功！\n执行的实例：' + datajson['data']['instanceUuid']
        else:
            data = '[CQ:face,id=151] 执行失败！\n原因：' + datajson.get('data')
        self.client.msg().raw(data)

    @RegCmd(
        name="启动服务器",
        usage="启动服务器",
        permission="ao",
        description="开启服务器",
        mode="MC服务器"
    )
    def start(self):
        setting = self.CheckAndGetSettings()
        if setting == 404:
            self.client.msg().raw('请先绑定服务器！\n绑定教程见作者B站：xzystudio1')
            return

        dataa = requests.get(
            url='{0}/api/protected_instance/open?uuid={1}&remote_uuid={2}&apikey={3}'.format(setting._get('MCSMApi'),
                                                                                             setting._get('MCSMUuid'),
                                                                                             setting._get('MCSMRemote'),
                                                                                             setting._get('MCSMKey')))
        datajson = dataa.json()

        if datajson['status'] == 200:
            data = '[CQ:face,id=54] 执行成功！\n执行的实例：' + datajson['data']['instanceUuid']
        else:
            data = '[CQ:face,id=151] 执行失败！\n原因：' + datajson.get('data')
        self.client.msg().raw(data)

    @RegCmd(
        name="面板数据",
        usage="面板数据",
        permission="ao",
        description="MCSM面板数据",
        mode="MC服务器"
    )
    def overview(self):
        try:
            setting = self.CheckAndGetSettings()
            if setting == 404:
                self.client.msg().raw('请先绑定服务器！\n绑定教程见作者B站：xzystudio1')
                return

            dataa = requests.get(
                url='{0}/api/overview?apikey={1}'.format(setting._get('MCSMApi'), setting._get('MCSMKey')))
            datajson = dataa.json()
            if datajson.get('status') == 200:
                data = '[CQ:face,id=54] 面板状态：正常\n[CQ:face,id=54] 面板版本：' + datajson.get('data').get(
                    'version') + '\n[CQ:face,id=54] cpu使用率：' + str(
                    datajson.get('data').get('process').get('cpu')) + '\n[CQ:face,id=54] 内存使用率：' + str(
                    self.hum_convert(
                        datajson.get('data').get('process').get('memory'))) + '\n[CQ:face,id=54] 面板登陆次数：' + str(
                    datajson.get('data').get('record').get('logined')) + '\n[CQ:face,id=54] 面板登陆失败次数：' + str(
                    datajson.get('data').get('record').get('loginFailed')) + '\n[CQ:face,id=54] ban ip次数：' + str(
                    datajson.get('data').get('record').get('banips')) + '\n[CQ:face,id=54] 当前系统时间：' + str(
                    datajson.get('data').get('system').get('time')) + '\n[CQ:face,id=54] 系统总共内存：' + str(
                    self.hum_convert(
                        datajson.get('data').get('system').get('totalmem'))) + '\n[CQ:face,id=54] 系统剩余内存：' + str(
                    self.hum_convert(
                        datajson.get('data').get('system').get('freemem'))) + '\n[CQ:face,id=54] 系统类型：' + str(
                    datajson.get('data').get('system').get('type')) + '\n[CQ:face,id=54] 主机名：' + str(
                    datajson.get('data').get('system').get('hostname'))
            else:
                data = '[CQ:face,id=151] {0}'.format(datajson.get('data'))

            self.client.msg().raw(data)
        except Exception as e:
            self.client.msg().raw("[CQ:face,id=189] 获取数据出错，请检查MCSMApi是否正确")

    @RegCmd(
        name="/",
        usage="/<指令内容>",
        permission="ao",
        description="在服务器里执行指令",
        mode="MC服务器"
    )
    def command(self, iff=True):
        message1 = self.data.message
        setting = self.CheckAndGetSettings()
        if setting == 404:
            setting = self.CheckAndGetSettingsSocket()
            if setting == 404:
                self.client.msg().raw('请先绑定服务器！\n绑定教程见作者B站：xzystudio1')
                return False

            self.sendSocket("command", {"cmd": self.data.message}, iff)
            return

        # 解码，需要指定原来是什么编码
        # message1 = message1.encode('gbk')
        # 拿unicode进行编码
        # message1 = temp_unicode.encode('gbk')
        # self.CrashReport(message1, uuid=123456789)

        try:
            dataa = requests.get(
                url='{0}/api/protected_instance/command?uuid={1}&remote_uuid={2}&apikey={3}&command={4}'.format(
                    setting._get('MCSMApi'), setting._get('MCSMUuid'), setting._get('MCSMRemote'), setting._get('MCSMKey'),
                    message1))
            datajson = dataa.json()
            if datajson['status'] == 200:
                data = '[CQ:face,id=54] 执行成功！'
            else:
                data = '[CQ:face,id=151] 执行失败！\n原因：' + datajson.get('data')
        except Exception as e:
            self.logger.warn(e, 'mcserver@command')
            data = f'[CQ:face,id=151] 执行失败！可能是MCSM面板不在线！'
        if iff:
            self.client.msg().raw(data)
            dataa = requests.get(url='{0}/api/protected_instance/outputlog?uuid={1}&remote_uuid={2}&apikey={3}'.format(
                setting._get('MCSMApi'), setting._get('MCSMUuid'), setting._get('MCSMRemote'),
                setting._get('MCSMKey'))).json().get("data")
            data = dataa.split("\r\n")[-2]
            data = re.sub(r'\x1b(\[.*?[@-~]|\].*?(\x07|\x1b\\))', "", data)
            data = re.sub(r'\[([0-9]+):([0-9]+):([0-9]+)\] \[(.*)/(.*)\]: ', "", data)
            data = f"[CQ:reply,id={self.data.se.get('message_id')}]{data}"
            self.client.msg().raw(data)

    def MCSMAddUser(self):
        setting = self.CheckAndGetSettings()
        if setting == 404:
            self.client.msg().raw('请先绑定服务器！\n绑定教程见作者B站：xzystudio1')
            return

        dataa = requests.get(url='{0}/api/instance?uuid={1}&remote_uuid={2}&apikey={3}'.format(setting._get('MCSMApi'),
                                                                                               setting._get('MCSMUuid'),
                                                                                               setting._get(
                                                                                                   'MCSMRemote'),
                                                                                               setting._get('MCSMKey')))

    @RegCmd(
        name="获取状态 ",
        usage="获取状态 <IP>:<端口>",
        permission="anyone",
        description="获取指定服务器的状态",
        mode="MC服务器"
    )
    def getStatus(self):
        ip = self.data.message.split(':')
        port = 25565 if ':' not in self.data.message else ip[1]
        ip = ip[0]

        data = requests.get(f'https://mcapi.us/server/status?ip={ip}&port={port}').json()
        if data.get('status') == 'success':
            if len(data.get('players').get('sample')) < 10:
                players = ''
                for i in data.get('players').get('sample'):
                    players += f"\n    {i.get('name')}"
            else:
                players = '\n    玩家数量过多，无法显示全部'
            self.client.msg(
                Statement('reply', id=self.data.se.get('message_id')),
                ImageStatement(f'https://mcapi.us/server/image?ip={ip}&port={port}'),
                FaceStatement(54), TextStatement(self.data.message, 1),
                FaceStatement(54), TextStatement(f'MOTD：{data.get("motd")}', 1),
                FaceStatement(54),
                TextStatement(f'在线玩家数：{data.get("players").get("now")}/{data.get("players").get("max")}', 1),
                FaceStatement(54), TextStatement(f'在线玩家：{players}', 1),
                FaceStatement(54), TextStatement(f'服务器版本：{data.get("server").get("protocol")}')
            ).send()
        else:
            self.client.msg(
                Statement('reply', id=self.data.se.get('message_id')),
                FaceStatement(54), TextStatement('获取失败！')
            ).send()

    @RegCmd(
        name="#",
        usage="#<message>",
        permission="anyone",
        description="同步服务器消息",
        mode="MC服务器",
        hidden=1
    )
    def sharpSync(self):
        self.data.message = 'say <' + str(self.data.se.get('sender').get('nickname')) + '> ' + self.parseMessage(self.data.message.lstrip('#'))
        self.command(False)
    
    def parseMessage(self, message):
        regexList = [
            [r"\[CQ:reply(.*?)\]", ""],
            [r"\[CQ:forward(.*?)\]", ""],
            [r"\[CQ:image(.*?),url=(.*?)\]", "[图片$1]", "url=(.*?)"],
            [r"\[CQ:face(.*?),id=(.*?)\]", r"[表情$1]", "id=(.*?)"],
            [r"\[CQ:record(.*?),url=(.*?)\]", r"[音频]"],
            [r"\[CQ:at,qq=(.*?)\]", r"@$1", r"qq=(\d+)"]
        ]

        for i in regexList:
            if "$" in i[1]:
                flag = True
                for l in i[1].split("$"):
                    self.logger.debug("Asz")
                    if flag:
                        flag = False
                        continue
                    num = int(l[0:1])
                    print(i[num+1])
                    pattern = re.compile(i[num+1], re.I)
                    m = pattern.match(message)
                    if m == None:
                        print(m, message, i[num+1])
                        continue
                    i[1] = i[1].replace(f"${num}", re.sub("(.*?)=", "", m.group(0)))
            
            message = re.sub(i[0], i[1], message)

        return message

    @RegCmd(
        name="MC服务器消息同步",
        usage="",
        permission="anyone",
        description="MC服务器消息同步",
        mode="MC服务器",
        type="message"
    )
    def syncMessage(self):
        # MC消息同步
        try:
            if self.data.groupSettings:
                if int(self.data.groupSettings._get('messageSync')) and str(self.data.message)[0:1] != '#':
                    message = self.data.message
                    self.data.message = 'say <' + str(self.data.se.get('sender').get('nickname')) + '> ' + self.parseMessage(message)
                    self.logger.debug(self.data.message)
                    if self.command(False) == False:
                        if random.randint(1, 5) == 3:
                            self.client.msg().raw("提示：关闭消息同步请发送： set messageSync===0")
                    self.data.message = message

            commandList = MCCmdModel()._get(qn=self.data.se.get("group_id"))
            for i in commandList:
                name = i.get("name")
                cmd = i.get("cmd")
                if self.data.message[0:len(name)] == name:
                    # 执行指令
                    # cmd = re.sub(r'\$([0-9])+', "", cmd)
                    for l in cmd.split():
                        try:
                            num = l.find("$")
                            if num != -1:
                                num = int(l[num + 1:num + 2])
                            else:
                                continue
                            if num > len(self.data.args) - 1:
                                self.client.msg().raw(f"参数不够，需要{num}个参数！")
                                return
                            cmd = cmd.replace(f"${num}", self.data.args[num])
                        except Exception:
                            pass

                    self.data.message = cmd
                    self.command()

        except Exception as e:
            pass

    def getuuid(self, name):
        mojangapi = 'https://api.mojang.com/users/profiles/minecraft/' + name
        page = urllib.request.urlopen(mojangapi)
        page = page.read()
        page = json.loads(page)
        dd = page['id']
        return dd.replace('"', '')


    def hyp(self):
        try:
            api = HypixelAPI("14cf35d1-87a2-4f64-a69b-3a2ee85ac7a0")
            player_dict = api.get_player_json(self.getuuid(self.data.message))
            self.client.msg().raw(player_dict)
        except Exception as e:
            self.client.msg().raw(traceback.format_exc())


    @RegCmd(
        name="加MC服务器指令",
        usage="加MC服务器指令",
        permission="ao",
        description="加MC服务器指令",
        mode="MC服务器"
    )
    def addMCCmd(self):
        gid = self.data.se.get('group_id')
        message = self.data.message

        ob = self.commandListener.get()
        if ob == 404:
            self.client.msg().raw('开始添加MC服务器指令，在此期间，你可以随时发送“退出”来退出加回复\n请发送在群中发送的指令')
            self.commandListener.set('mcserver@addMCCmd', {'name': ''})
            return True

        step = int(ob.get('step'))
        args = ob.get('args')

        if step == 1:
            self.commandListener.set(args={'name': message})
            self.client.msg().raw(
                '请发送在服务端执行的指令，使用“$数字”代替玩家输入的参数，请注意执行指令是在控制台执行，请自行斟酌指令前是否带“/”')

        if step == 2:
            self.commandListener.remove()

            MCCmdModel()._insert(name=args.get("name"), cmd=message, qn=gid)
            self.client.msg().raw('添加成功！')


    @RegCmd(
        name="MC服务器指令",
        usage="MC服务器指令",
        permission="ao",
        description="列出所有MC服务器指令",
        mode="MC服务器"
    )
    def listMCCmd(self):
        arr = []
        commandList = MCCmdModel()._get(qn=self.data.se.get("group_id"))
        for i in commandList:
            arr.append({"type": "node",
                        "data": {"name": self.data.botSettings._get("name"), "uin": self.data.botSettings._get("myselfqn"),
                                 "content": "{} => {}".format(i.get("name"), i.get("cmd"))}})
        self.client.CallApi("send_group_forward_msg", {"group_id": self.data.se.get("group_id"), "messages": arr})


    @RegCmd(
        name="删MC服务器指令",
        usage="删MC服务器指令 <群中指令名>",
        permission="ao",
        description="删MC服务器指令",
        mode="MC服务器"
    )
    def delMCCmd(self):
        MCCmdModel()._delete(qn=self.data.se.get("group_id"), name=self.data.message)
        self.client.msg().raw("face54 删除成功！")
