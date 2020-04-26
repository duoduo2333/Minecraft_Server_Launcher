import sys
import subprocess
import threading
import os
from PyQt5.QtCore import QThread, pyqtSignal
import time
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QMessageBox
import ui
import ctypes
import requests
import json
import pickle
import webbrowser

#当前版本
curversion = 1.0

#提示框类
class Msgbox(QWidget):
    def __init__(self):
        super().__init__()
    def info(self, title, text):
        QMessageBox.information(self, title, text)
    def question(self, title, text):
        if QMessageBox.question(self, title, text, QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes) == QMessageBox.Yes:
            return True
        else:
            return False

#隐藏控制台
def hideConsole():
  whnd = ctypes.windll.kernel32.GetConsoleWindow()
  if whnd != 0:
    ctypes.windll.user32.ShowWindow(whnd, 0)
    # if you wanted to close the handles...
    #ctypes.windll.kernel32.CloseHandle(whnd)

#显示控制台
def showConsole():
  whnd = ctypes.windll.kernel32.GetConsoleWindow()
  if whnd != 0:
    ctypes.windll.user32.ShowWindow(whnd, 1)

#进入server目录
if not(os.path.isdir("server")):
    os.mkdir("server")
os.chdir("server")

dl_list = [] #服务端列表
settings = {} #设置

#下载
class Download(QThread):
    progress = pyqtSignal(float)
    dl_info = pyqtSignal(str)
    
    def __init__(self):
        self.isrunning = False
        self.dl_file = ""
        self.dl_path = ""
        self.stop_dl = False
        super(Download, self).__init__()
    
    def start(self, url, filename="server.jar"):
        if self.isrunning:
            msgbox.info("提示","请等待当前下载任务结束")
        else:
            #下载线程
            def dl():
                self.isrunning = True
                try:
                    self.dl_info.emit("正在开始下载...")
                    self.url = url
                    self.response_data_file = requests.get(url, stream=True)
                    self.content_size = int(self.response_data_file.headers['content-length'])/1048576
                    self.filename = filename+".jar"
                    self.size = 0
                    self.start_time = time.time()
                    with open(self.filename, 'wb') as f:
                        for chunk in self.response_data_file.iter_content(chunk_size=131072):
                            if self.stop_dl == True:
                                self.stop_dl = False
                                break
                            if chunk:
                                self.nprogress = self.size / self.content_size
                                if 0 <= self.nprogress <= 99:
                                    self.progress.emit(self.nprogress)
                                self.size += 0.125
                                time.sleep(0.05)
                                self.dl_info.emit("已下载："+str(self.size)+"MB 下载速度："+str(round(0.125/(time.time()-self.start_time),2))+"mb/s")
                                f.write(chunk)
                            self.start_time = time.time()
                except requests.exceptions.ConnectionError:
                    self.dl_info.emit("网络错误")
                else:
                    self.progress.emit(1.0)
                self.dl_info.emit("当前没有下载任务")
                self.isrunning = False
            
            threading.Thread(target=dl).start() #启动线程
    def stop(self):
        if self.isrunning:
            self.stop_dl = True
            for i in range(5):
                time.sleep(0.1)
                if self.stop_dl == False:
                    self.isrunning = False
                    self.dl_info.emit("当前没有下载任务")
                    msgbox.info("提示","已停止当前下载任务")
                    break
        else:
            msgbox.info("提示","当前没有下载任务")

#服务器
class Server(QThread):
    sig = pyqtSignal(str)
    def __init__(self):
        self.isrunning = False
        super(Server, self).__init__()

    def start(self, path="server.jar", ram="1024"):
        self.path = path
        self.ram = ram
        if self.isrunning:
            self.sig.emit("服务器已经在运行了")
        else:
            self.sig.emit("服务器开始运行".center(30,"="))
            self.sig.emit("正在启动服务器，请耐心等待...")
            self.isrunning = True
            if not(os.path.isfile(self.path)):
                self.sig.emit("服务端"+path+"不存在。请检查\"配置\"选项卡中的服务端核心设置。")
            self.p = subprocess.Popen("java -Xmx"+self.ram+"M -Xms"+self.ram+"M -jar \""+self.path+"\" nogui",
                                 shell=True,
                                 stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE)
            self.pid = self.p.pid
            
            def output():
                lines = 0
                for i in iter(self.p.stdout.readline,'b'):
                    if not i:
                        if lines == 0:
                            self.sig.emit("错误：请检查服务器核心是否正确。")
                        self.isrunning = False
                        self.sig.emit("服务器停止运行".center(30,"="))
                        break
                    if i.decode('gbk').find("EULA") > 0 and lines < 40:
                        self.sig.emit("检测到服务器异常：你必须同意EULA才能继续。转到\"配置\"页\"一键同意协议\"")
                    self.sig.emit(i.decode('gbk')[0:-2])
                    lines += 1
                    #print_log(i.decode('gbk'))
                    time.sleep(0.1)
            threading.Thread(target=output).start()
            
    def runcmd(self,cmd):
        if self.isrunning:
            self.p.stdin.write((cmd+"\r\n").encode())
            self.p.stdin.flush()
        else:
            self.sig.emit("服务器不在运行，命令执行失败")

    def stop(self):
        if self.isrunning:
            self.runcmd("stop")
        else:
            self.sig.emit("服务器不在运行")

def start_server():
    if ui.jar_list.count() == 0:
        mcserver.start()
    else:
        mcserver.start(path=ui.jar_list.currentText(), ram=str(ui.max_ram.value()))

def print_log(text):
    ui.log.append(text)
    QApplication.processEvents()

def stop_server():
    mcserver.stop()

def clear_log():
    ui.log.clear()

def runcmd():
    print_log(">>>"+ui.cmdbox.text())
    mcserver.runcmd(ui.cmdbox.text())
    ui.cmdbox.setText("")

def fresh_jar():
    jar_list = []
    ui.jar_list.clear()
    for eachfile in os.listdir(path='.'):
        if os.path.splitext(eachfile)[1] == ".jar":
            jar_list.append(eachfile)
    ui.jar_list.addItems(jar_list)

def cur_info():
    if mcserver.isrunning:
        msgbox.info("服务器信息","服务端核心："+mcserver.path+"\n内存："+mcserver.ram+"\n进程PID ："+str(mcserver.pid))
    else:
        msgbox.info("服务器信息","当前服务器不在运行。")

def pause_dl():
    msgbox.info("提示","不支持断点续传")

def fresh_dl_list():
    global dl_list
    try:
        dl_list.clear()
        dl_list = requests.get("https://gitee.com/duoduo233/minecraft-server-launcher/raw/master/download.json").text
        dl_list = json.loads(dl_list)
        ui.dl_list.clear()
        ui.dl_list.addItems(list(dl_list))
    except requests.exceptions.ConnectionError:
        msgbox.info("错误","获取下载连接失败，请检查网络连接是否正确")

def dl_progress(progress):
    ui.progress.setValue(int(progress*100))

def dl_info(text):
    if text == "网络错误":
        msgbox.info("错误","网络连接错误，下载失败")
    ui.downloading.setText(text)

def download():
    if len(dl_list) != 0:
        if ui.dl_list.currentItem() != None:
            dl.start(dl_list[ui.dl_list.currentItem().text()], filename=ui.dl_list.currentItem().text())
        else:
            msgbox.info("错误","请先选择要下载的文件")
    else:
        msgbox.info("错误","请先点击刷新列表")

def show_dl_info():
    if dl.isrunning:
        msgbox.info("提示","文件大小："+str(dl.content_size)+\
                    "\n文件地址："+dl.url+\
                    "\n下载位置：\\server\\"+dl.filename)
    else:
        msgbox.info("提示","当前没有下载任务")

def loadSettings():
    global settings
    settings.clear()
    if os.path.isfile("..\\settings.pickle"):
        with open("..\\settings.pickle", "rb") as file:
            settings = pickle.load(file)
    else:
        settings = {"debug":"False",
        "auto_update":"True",
        "jar":"server.jar",
        "ram":1024}

    try:
        if settings["debug"] == "True":
            ui.debug.setChecked(True)
        else:
            ui.debug.setChecked(False)
        
        ui.jar_list.clear()
        ui.jar_list.addItems([settings["jar"]])
        
        if settings["auto_update"] == "True":
            ui.auto_update.setChecked(True)
        else:
            ui.auto_update.setChecked(False)
        
        ui.max_ram.setValue(settings["ram"])
    except KeyError:
        msgbox.info("提示","软件配置文件错误，可能是由于软件升级导致的，已重置配置文件")
        reset_setting()
        
def saveSettings():
    global settings
    settings.clear()
    
    settings["jar"] = ui.jar_list.currentText()
    
    settings["ram"] = ui.max_ram.value()

    if ui.debug.isChecked():
        settings["debug"] = "True"
    else:
        settings["debug"] = "False"
    
    if ui.auto_update.isChecked():
        settings["auto_update"] = "True"
    else:
        settings["auto_update"] = "False"
    
    #写入到文件
    with open("..\\settings.pickle", "wb") as file:
        pickle.dump(settings, file)

def tabChanged():
    if ui.tabWidget.currentIndex() != 1:
        saveSettings()
        print("自动保存配置文件")

def checkUpdate():
    try:
        verinfo = requests.get("https://gitee.com/duoduo233/minecraft-server-launcher/raw/master/latest.json").text
        verinfo = json.loads(verinfo)
        if curversion < float(verinfo["latest"]):
            #有可用更新
            if msgbox.question("提示", "发现可用更新，是否去下载？\n版本："+str(curversion)+"->"+verinfo["latest"]+"\n更新说明：\n"+verinfo["info"]):
                #去下载
                webbrowser.open(verinfo["url"], new=0, autoraise=True) 
            if verinfo["old_version"] == "False":
                #强制更新
                msgbox.info("提示","当前版本过低，请更新后再使用\n下载地址："+verinfo["url"])
                sys.exit()
        else:
            msgbox.info("提示","当前已经是最新版本了")
    except requests.exceptions.ConnectionError:
        msgbox.info("错误", "检查更新失败，请检查网络连接是否正确")

def old_ver():
    try:
        verinfo = requests.get("https://gitee.com/duoduo233/minecraft-server-launcher/raw/master/latest.json").text
        verinfo = json.loads(verinfo)
        if curversion < float(verinfo["latest"]):
            if verinfo["old_version"] == "False":
                #强制更新
                msgbox.info("提示","当前版本过低，请更新后再使用\n下载地址："+verinfo["url"])
                webbrowser.open(verinfo["url"], new=0, autoraise=True)
                sys.exit()
    except requests.exceptions.ConnectionError:
        print("网络连接失败")

def open_server_path():
    os.system("explorer.exe "+os.getcwd())

def about():
    msgbox.info("关于","当前版本："+str(curversion)+\
        "\n作者：多多"+\
        "\n问题反馈：duoduo233@hotmail.com"+\
        "\n本软件永久免费，严禁倒卖")

def eula():
    if msgbox.question("提示", "是否同意此协议？https://account.mojang.com/documents/minecraft_eula"):
        with open("eula.txt", "w") as f:
            f.write("eula=true")
        msgbox.info("提示","server\\eula.txt修改成功")
    else:
        msgbox.info("提示","必须同意此协议才能继续开服")

def open_pro():
    if os.path.isfile("server.properties"):
        os.system("start server.properties")
    else:
        msgbox.info("提示","server\\server.properties不存在")

def help_pro():
    webbrowser.open("https://wiki.biligame.com/mc/Server.properties#Java.E7.89.88_3", new=0, autoraise=True)

def del_pro():
    if mcserver.isrunning == True:
        msgbox.info("提示","当前服务器正在运行，停止服务器后再试")
    else:
        if os.path.isfile("server.properties"):
            os.remove("server.properties")
            msgbox.info("提示","已删除服务器配置文件，下次启动服务器时会自动创建")
        else:
            msgbox.info("提示","服务器配置文件server.properties不存在")

def save_map():
    if mcserver.isrunning:
        mcserver.runcmd("save-all")
        msgbox.info("提示","保存地图命令已发送")
    else:
        msgbox.info("提示","服务器不在运行")

def reset_setting():
    if os.path.isfile("..\\settings.pickle"):
        os.remove("..\\settings.pickle")
    loadSettings()
    msgbox.info("提示","设置重置成功")
    
def java_help():
    webbrowser.open("https://www.baidu.com/s?wd=java%20%E7%8E%AF%E5%A2%83%E5%8F%98%E9%87%8F")

#实例化服务器
mcserver = Server()
mcserver.sig.connect(print_log)

#实例化下载
dl = Download()
dl.progress.connect(dl_progress)
dl.dl_info.connect(dl_info)

#主窗口类
class MyWindow(QMainWindow, ui.Ui_MainWindow):
    def __init__(self, parent=None):
        super(MyWindow, self).__init__(parent)
        self.setupUi(self)
    def closeEvent(self, event):
        if mcserver.isrunning == True:
            if msgbox.question("提示","服务器正在运行，关闭本软件会导致服务器无法关闭， 是否继续关闭本软件？") == True:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

app = QApplication(sys.argv)
ui = MyWindow()
ui.show()

#ui事件
ui.start_server.clicked.connect(start_server) #启动服务器
ui.stop_server.clicked.connect(stop_server) #停止服务器
ui.clear_log.clicked.connect(clear_log) #清楚日志
ui.run.clicked.connect(runcmd) #执行命令
ui.fresh_jar.clicked.connect(fresh_jar) #刷新服务端
ui.info.triggered.connect(cur_info) #服务器信息
ui.pause_dl.clicked.connect(pause_dl) #暂停下载
ui.continue_dl.clicked.connect(pause_dl) #继续下载
ui.fresh_dl_list.clicked.connect(fresh_dl_list) #刷新下载列表
ui.download.clicked.connect(download) #下载
ui.cancel_dl.clicked.connect(dl.stop) #取消下载
ui.dl_info.clicked.connect(show_dl_info) #下载信息
ui.save_setting.clicked.connect(saveSettings) #保存设置
ui.tabWidget.currentChanged.connect(tabChanged) #标签页更换
ui.update.triggered.connect(checkUpdate) #检查更新
ui.server_path.triggered.connect(open_server_path) #打开服务器所在位置
ui.about.triggered.connect(about) #关于
ui.eula.clicked.connect(eula) #一键同意协议
ui.open_pro.clicked.connect(open_pro) #打开配置文件
ui.help_pro.clicked.connect(help_pro) #配置文件帮助
ui.del_pro.clicked.connect(del_pro) #重置配置文件
ui.save_map.clicked.connect(save_map) #保存地图
ui.reset_setting.clicked.connect(reset_setting) #重置设置
ui.java_help.clicked.connect(java_help) #java环境变量

loadSettings()

msgbox = Msgbox()

#隐藏命令行
if settings["debug"] == "False":
    hideConsole()
else:
    print("mc_server_launcher v0.1")
    print("已启用调试模式。若不想看到此窗口，可以到“配置”标签页中关闭调试模式。")

if settings["auto_update"] == "True":
    checkUpdate()
else:
    old_ver()

sys.exit(app.exec_())
