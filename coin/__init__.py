from pbf.controller.PBF import PBF
from pbf.utils.CQCode import CQCode
from pbf.utils.Coin import Coin
from pbf.utils.RegCmd import RegCmd
from pbf.model.UserInfoModel import UserInfoModel, CidUserInfoModel

_name = "好感度系统扩展"
_version = "1.0.1"
_description = "扩展猪比自带的好感度系统，更加便利！"
_author = "xzyStudio"
_cost = 0.00


class coin(PBF):
    @RegCmd(
        name="绑定频道",
        usage="绑定频道",
        permission="anyone",
        description="将正常QQ号与频道绑定",
        mode="好  感  度"
    )
    def bangding(self):
        uid = self.data.se.get('user_id')
        gid = self.data.se.get('group_id')
        message = self.data.message

        if len(self.data.args) == 1:
            if gid != None:
                self.client.msg().raw('请在频道中发送“绑定频道”')
            else:
                self.client.msg().raw(
                    '[CQ:at,qq=' + str(uid) + '] 请在任意地方（除频道外）发送“绑定频道 ' + str(uid) + '”（不包括双引号）')
        else:
            value = self.data.args[1]
            UserInfoModel(qn=uid)._set(cid=value)
            self.client.msg().raw('绑定成功！')

    @RegCmd(
        name="投食",
        usage="投食",
        permission="anyone",
        description="喂一喂小猪比",
        mode="好  感  度"
    )
    def toushi(self):
        uid = self.data.se.get('user_id')
        gid = self.data.se.get('group_id')
        cid = self.data.se.get('channel_id')
        uuid = self.data.uuid
        coinlist = None

        if cid != None:
            coinlist = CidUserInfoModel(cid=cid, uuid=uuid)
        else:
            coinlist = UserInfoModel(qn=uid, uuid=uuid)

        if not coinlist.exists:
            self.client.msg().raw('您还没有注册！\n快发送“注册”让{0}认识你吧'.format(self.data.botSettings._get('name')))
            return
        if coinlist._get('toushi') == 0:
            coinlist._set(toushi=1)
            self.client.msg().raw('投食成功！\n获得' + str(Coin(self.data).add()) + '个好感度qwq')
        else:
            self.data.message = '不要贪心啊，你已经投过食啦！'
            self.client.msg().raw(self.data.message)
            # zhuan()

    @RegCmd(
        name="注册",
        usage="注册",
        permission="anyone",
        description="注册用户",
        mode="好  感  度"
    )
    def zhuce(self, sendFlag=1):
        uid = self.data.se.get('user_id')
        gid = self.data.se.get('group_id')
        userCoin = self.data.userCoin
        cid = self.data.se.get('channel_id')

        if cid is not None:
            if sendFlag:
                self.client.msg().raw('请不要在频道里注册！')
            return False

        if userCoin == -1:
            UserInfoModel(uuid=self.data.uuid, qn=uid, value=self.data.botSettings._get("defaultCoin"))
            self.logger.info('注册用户' + str(uid), '好  感  度')
            if gid != None and sendFlag:
                self.client.msg().raw('[CQ:face,id=54] 注册成功！')

            return self.data.botSettings._get('defaultCoin')
        else:
            self.client.msg().raw('{0}已经认识你了呢qwq'.format(self.data.botSettings._get('name')))
            return userCoin

    @RegCmd(
        name="加好感度 ",
        usage="加好感度 <QQ号或者@那个人>[ <要加的个数，不指定则随机数>]",
        permission="owner",
        description="给用户加好感度",
        mode="好  感  度"
    )
    def addCoinFunc(self):
        uid = self.data.se.get('user_id')
        gid = self.data.se.get('group_id')
        message = self.data.message

        if ' ' in message:
            message = message.split(' ')
            userid = message[0]
            num = message[1]
            if 'at' in userid:
                userid = CQCode(self.data.message).get('qq')[0]
            self.data.se['user_id'] = userid
            userCoin = int(UserInfoModel(uuid=self.data.uuid, qn=userid)._get("value"))

            self.data.userCoin = userCoin
            coin = Coin(self.data)

            userCoin = coin.add(num)
        else:
            userid = message
            self.data.se['user_id'] = userid
            userCoin = int(UserInfoModel(uuid=self.data.uuid, qn=userid)._get("value"))

            self.data.userCoin = userCoin
            coin = Coin(self.data)

            userCoin = coin.add()

        if userCoin == False:
            return self.client.msg().raw('用户未注册')
        self.client.msg().raw('[CQ:face,id=54] 成功给用户{0}添加{1}个好感度'.format(userid, userCoin))