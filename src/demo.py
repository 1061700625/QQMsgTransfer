import json
import requests
from flask import Flask
from time import sleep


class Logger:
    def __init__(self, level='debug'):
        self.level = level

    def DebugLog(self, *args):
        if self.level == 'debug':
            print(*args)

    def TraceLog(self, *args):
        if self.level == 'trace':
            print(*args)

    def setDebugLevel(self, level):
        self.level = level.lower()


class QQBot:
    def __init__(self):
        self.addr = 'http://127.0.0.1:8080/'

    def getSession(self, auth_key):
        """每个Session只能绑定一个Bot，但一个Bot可有多个Session。
        session Key在未进行校验的情况下，一定时间后将会被自动释放"""
        data = {"authKey": auth_key}
        url = self.addr+'auth'
        res = requests.post(url, data=json.dumps(data)).json()
        logger.DebugLog(res)
        if res['code'] == 0:
            return res['session']
        return None

    def verifySession(self, session, qq):
        """校验并激活Session，同时将Session与一个已登录的Bot绑定"""
        data = {"sessionKey": session, "qq": qq}
        url = self.addr + 'verify'
        res = requests.post(url, data=json.dumps(data)).json()
        logger.DebugLog(res)
        if res['code'] == 0:
            return True
        return False

    def releaseSession(self, session, qq):
        """不使用的Session应当被释放，长时间（30分钟）未使用的Session将自动释放，
        否则Session持续保存Bot收到的消息，将会导致内存泄露(开启websocket后将不会自动释放)"""
        data = {"sessionKey": session, "qq": qq}
        url = self.addr + 'release'
        res = requests.post(url, data=json.dumps(data)).json()
        logger.DebugLog(res)
        if res['code'] == 0:
            return True
        return False

    def getMsgFromGroup(self, session):
        url = self.addr + 'fetchLatestMessage?count=10&sessionKey='+session
        res = requests.get(url).json()
        if res['code'] == 0:
            return res['data']
        return None

    def parseGroupMsg(self, data):
        res = []
        if data is None:
            return res
        for item in data:
            if item['type'] == 'GroupMessage':
                type = item['messageChain'][1]['type']
                if type == 'Image':
                    text = item['messageChain'][1]['url']
                elif type == 'Plain':
                    text = item['messageChain'][1]['text']
                elif type == 'Face':
                    text = item['messageChain'][1]['faceId']
                else:
                    logger.TraceLog(">> 当前消息类型暂不支持转发：=> "+type)
                    continue
                name = item['sender']['memberName']
                group_id = str(item['sender']['group']['id'])
                group_name = item['sender']['group']['name']
                res.append({'text': text, 'type': type, 'name': name, 'groupId': group_id, 'groupName': group_name})
        return res

    def getMessageCount(self, session):
        url = self.addr + 'countMessage?sessionKey='+session
        res = requests.get(url).json()
        if res['code'] == 0:
            return res['data']
        return 0

    def sendMsgToGroup(self, session, group, msg):
        text = msg['text']
        type = msg['type']
        name = msg['name']
        group_id = msg['groupId']
        group_name = msg['groupName']
        content1 = "用户：{}\n群号：{}\n群名：{}\n消息：{}".format(
            name, group_id, group_name, text)
        content2 = "用户：{}\n群号：{}\n群名：{}\n消息：\n".format(
            name, group_id, group_name)
        if type == 'Plain':
            message = [{"type": type, "text": content1}]
        elif type == 'Image':
            message = [
                {"type": 'Plain', "text": content2},
                {"type": type, "url": text}]
        elif type == 'Face':
            message = [{"type": 'Plain', "text": content2},
                       {"type": type, "faceId": text}]
        else:
            logger.TraceLog(">> 当前消息类型暂不支持转发：=> "+type)
            return 0
        data = {
                "sessionKey": session,
                "group": group,
                "messageChain": message
                }
        url = self.addr + 'sendGroupMessage'
        res = requests.post(url, data=json.dumps(data)).json()
        if res['code'] == 0:
            return res['messageId']
        return 0

    def sendMsgToAllGroups(self, session, receive_groups, send_groups, msg_data):
        # 对每条消息进行检查
        for msg in msg_data:
            group_id = msg['groupId']
            # 接收的消息群正确（目前只支持 消息类型）
            if group_id in receive_groups:
                # 依次将消息转发到目标群
                for g in send_groups:
                    if g == group_id:
                        continue
                    res = self.sendMsgToGroup(session, g, msg)
                    if res != 0:
                        logger.TraceLog(">> 转发成功！{}".format(g))


logger = Logger()
if __name__ == '__main__':
    with open('conf.json', 'r+', encoding="utf-8") as f:
        content = f.read()
    conf = json.loads(content)

    auth_key = conf['auth_key']
    bind_qq = conf['bind_qq']
    receive_groups = conf['receive_groups']
    send_groups = conf['send_groups']
    sleep_time = conf['sleep_time']
    debug_level = conf['debug_level']
    # receive_groups = ['537241540', '719684243']
    # send_groups = ['537241540', '719684243']

    logger.setDebugLevel(debug_level)

    bot = QQBot()
    session = bot.getSession(auth_key)
    logger.DebugLog(">> session: "+session)
    bot.verifySession(session, bind_qq)
    while True:
        cnt = bot.getMessageCount(session)
        if cnt:
            logger.DebugLog('>> 有消息了 => {}'.format(cnt))
            logger.DebugLog('获取消息内容')
            data = bot.getMsgFromGroup(session)
            logger.DebugLog('解析消息内容')
            data = bot.parseGroupMsg(data)
            logger.DebugLog('转发消息内容')
            bot.sendMsgToAllGroups(session, receive_groups, send_groups, data)
        # else:
        #     logger.DebugLog('空闲')
        sleep(sleep_time)
    bot.releaseSession(session, bind_qq)


