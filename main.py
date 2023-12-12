import json
import os

import sys
from datetime import date, datetime, time
import cv2
import re

from PyQt5 import uic, QtGui
from PyQt5.Qt import *
from PyQt5.QtGui import QColor

from ui.LabelUI3 import Ui_MainWindow as labelwinui
from ui.LoginUI import Ui_MainWindow as loginwinui
from ui.UserUI import Ui_MainWindow as userwinui
from ui.AdminUI import Ui_MainWindow as adminwinui
from ui.ModifyUI import Ui_MainWindow as modifywinui

import pymysql
from xpinyin import Pinyin


def database_connect(username, password):
    global cnx, cursor
    p = Pinyin()
    name_pinyin = p.get_initials(username, '').lower()  # 系统登录名为姓名全称，数据库登录名为姓名缩写
    try:
        cnx = pymysql.connect(host="e73cf760cbf2.c.methodot.com",
                              port=30960,
                              user=name_pinyin,
                              passwd=password,
                              database="labelsystem_database")
        cursor = cnx.cursor()
        '''
        cnx = pymysql.connect(host="bj-cdb-0yrrrs1u.sql.tencentcdb.com",
                              port=63803,
                              user=name_pinyin,
                              passwd=password,
                              database="labelsystem_database")
        cursor = cnx.cursor()
        '''
        print("数据库连接成功：user=" + name_pinyin, ",passwd=" + password)
    except pymysql.Error as e:
        error_message = str(e)
        print("无法连接到数据库：", error_message)
        raise


# 登录界面
class LoginWin(QMainWindow, loginwinui):
    login_signal = pyqtSignal(str, str, str)

    def __init__(self):
        QMainWindow.__init__(self)
        loginwinui.__init__(self)
        self.setupUi(self)

        self.login_username = ""
        self.login_password = ""
        self.login_method = ""

        self.username.setText("")
        self.password.setText("")

        if os.path.exists("login_info.txt"):
            f = open("login_info.txt", "r", encoding="utf-8")
            login_info = f.readline().split(":")
            self.username.setText(login_info[0])
            self.password.setText(login_info[1])

        self.init()
        self.btnBind()

    def init(self):
        self.setWindowIcon(QIcon("icon/pen.png"))
        self.logo.setPixmap(QPixmap("icon/logo.PNG"))
        self.logo.setScaledContents(True)

    def btnBind(self):
        self.pushButton.clicked.connect(self.login)

    def login(self):

        self.login_username = self.username.text()
        self.login_password = self.password.text()
        self.login_method = self.method.currentText()

        # 账户名为空
        if not self.login_username:
            QMessageBox.warning(None, "提示", "请填写账户名！")
        if not self.login_password:
            QMessageBox.warning(None, "提示", "请填写密码！")

        # 连接数据库
        database_connect(self.login_username, self.login_password)

        query = "INSERT IGNORE INTO attendance (name, date,daily_work_time) VALUES (%s, %s, %s) "
        values = (self.login_username, date.today(), '0:0:0')
        cursor.execute(query, values)
        cnx.commit()

        f = open("login_info.txt", "w", encoding="utf-8")
        f.write(self.login_username + ":" + self.login_password)

        query = "SELECT * FROM user where name=%s"
        values = self.login_username
        cursor.execute(query, values)
        res = cursor.fetchall()
        print("identity:", res[0][2])

        if res[0][2] == "admin":
            if self.login_method == "标注模式":
                self.labelWin = LabelWin()
                self.login_signal.connect(self.labelWin.login_slot)
                self.login_signal.emit(self.login_username, self.login_password, self.login_method)
                self.labelWin.show()
                self.close()
            elif self.login_method == "审核模式":
                self.labelWin = LabelWin()
                self.login_signal.connect(self.labelWin.login_slot)
                self.login_signal.emit(self.login_username, self.login_password, self.login_method)
                self.labelWin.show()
                self.close()
            elif self.login_method == "管理模式":
                self.adminWin = AdminWin()
                self.adminWin.show()
                self.close()
        if res[0][2] == "normal":
            if self.login_method == "标注模式":
                self.labelWin = LabelWin()
                self.login_signal.connect(self.labelWin.login_slot)
                self.login_signal.emit(self.login_username, self.login_password, self.login_method)
                self.labelWin.show()
                self.close()
            elif self.login_method == "审核模式":
                self.labelWin = LabelWin()
                self.login_signal.connect(self.labelWin.login_slot)
                self.login_signal.emit(self.login_username, self.login_password, self.login_method)
                self.labelWin.show()
                self.close()
            elif self.login_method == "管理模式":
                QMessageBox.warning(None, "提示", "您不是管理员！")


class ComboBoxSignal(QObject):
    value_changed = pyqtSignal(str)


# 标注界面
class LabelWin(QMainWindow, labelwinui):
    my_signal = pyqtSignal(str)
    user_signal = pyqtSignal(str, str, str, int, int, int, int)
    combo_signal = ComboBoxSignal()
    modify_signal = pyqtSignal(str, str)

    def __init__(self):
        QMainWindow.__init__(self)
        labelwinui.__init__(self)
        self.search_relation_head = None
        self.search_relation_data = None
        self.search_relation_video_name = None
        self.search_relation_uid = None
        self.search_relation_flag = None
        self.time_delta = None
        self.work_end_time = None
        self.work_start_time = None
        self.elapsed_second = None
        self.elapsed_minute = None
        self.elapsed_milliseconds = None
        self.is_working = False
        self.setupUi(self)

        self.start_work_time = QTime(0, 0, 0)
        self.elapsed_work_time = QTime(0, 0, 0)
        self.hour = 0
        self.minute = 0
        self.second = 0
        self.label_count = 0
        self.check_count = 0

        self.result = None
        self.folder_dirname = ""
        self.table_row = 0  # 鼠标选中的行
        self.table_col = 0  # 鼠标选中的列
        self.path_txt = ""  # result_txt路径
        self.path_json = ""  # result_json路径
        self.folder = ""  # 视频目录
        self.rList = []
        self.info = {}

        self.flag = 0  # 是否已导入视频

        # 视频计时器
        self.timer = QTimer()
        self.timer.timeout.connect(self.playVideo)

        # 当前时间计时器
        self.system_timer = QTimer()
        self.system_timer.timeout.connect(self.updateSysTime)

        # 标注时间计时器
        self.work_timer = QTimer()
        self.work_timer.timeout.connect(self.updateWorkTime)

        self.last_click_time = QElapsedTimer()  # 记录上次点击时间

        self.ten_min_timer = QTimer()
        self.ten_min_timer.timeout.connect(self.timer_timeout)

        # 创建一个QMediaPlayer并将它与QVideoWidget相连
        self.media_player = QMediaPlayer(self)
        self.ui = uic.loadUi('ui/LabelUI.ui')
        self.media_player.setVideoOutput(self.ui.widget)

        self.setupUi(self)
        self.init()
        self.signals()
        self.btnBind()

        self.system_timer.start(1000)

    # 初始化
    def init(self):
        # self.logo.setPixmap(QPixmap("icon/logo.PNG"))
        # self.logo.setScaledContents(True)
        # self.clear.setVisible(False)
        # self.user_picture1.setPixmap(QPixmap("icon/user.PNG"))
        # self.user_picture1.setScaledContents(True)

        self.user_picture.setStyleSheet("QPushButton{border-image: url(icon/user.png)}")  # 绑定图片
        # self.import_videos.setVisible(False)
        # self.import_video.setVisible(False)
        self.setWindowIcon(QIcon("icon/pen.png"))

        if not os.path.exists("results"):
            os.mkdir("results")
            if not os.path.exists("results/json"):
                os.mkdir("results/json")
            if not os.path.exists("results/txt"):
                os.mkdir("results/txt")

        self.updateSysTime()
        self.work_time.setText("00:00:00")

    # 信号槽绑定
    def signals(self):
        self.my_signal.connect(self.signal_slot)
        self.check_result.currentTextChanged.connect(self.on_value_changed)
        self.combo_signal.value_changed.connect(self.on_value_change_detected)

    def on_value_changed(self, value):
        self.combo_signal.value_changed.emit(value)

    def on_value_change_detected(self, value):
        print("checks result:", value)
        if value == "other":
            # self.result_frame.setEnabled(True)
            self.label_10.setEnabled(True)
            self.label_2.setEnabled(True)
            self.Head_ID.setEnabled(True)
            self.relation.setEnabled(True)

        else:
            # self.result_frame.setEnabled(False)
            self.label_10.setEnabled(False)
            self.label_2.setEnabled(False)
            self.Head_ID.setEnabled(False)
            self.relation.setEnabled(False)

    # 槽函数，接收登录信息
    def login_slot(self, username, password, method):
        self.username = username
        self.password = password
        self.method = method
        print(username)
        self.login_name.setText(self.username)
        self.login_method.setText(self.method)
        print("login:", self.username, self.method)

        if method == "标注模式":
            '''
            self.check_frame.setVisible(False)
            self.result_frame.setEnabled(True)
            '''
            # self.check.setVisible(False)
            self.submit.setText("提交标注")
            self.check_result.setVisible(False)
            # self.submit.setVisible(True)
            self.same.setVisible(True)

            self.label_10.setEnabled(True)
            self.label_2.setEnabled(True)
            self.Head_ID.setEnabled(True)
            self.relation.setEnabled(True)

            self.import_all.setVisible(True)

            self.check_reason.setVisible(False)
            self.check_reason_txt.setVisible(False)
            # self.modify_label.setVisible(True)

            self.modify_label.setText("待修改标注")
            self.modify.setVisible(True)
            self.to_be_labeled.setVisible(False)
            self.to_be_checked.setVisible(False)
        if method == "审核模式":
            '''
            self.check_frame.setVisible(True)
            self.result_frame.setEnabled(False)
            '''
            # self.check.setVisible(True)s
            self.submit.setText("提交审核")
            self.check_result.setVisible(True)
            # self.submit.setVisible(False)
            self.same.setVisible(False)

            self.label_10.setEnabled(False)
            self.label_2.setEnabled(False)
            self.Head_ID.setEnabled(False)
            self.relation.setEnabled(False)

            self.import_all.setVisible(False)
            self.check_reason.setVisible(True)
            self.check_reason_txt.setVisible(True)

            # self.modify_label.setVisible(False)
            self.modify_label.setText("处理申诉")
            self.modify.setVisible(False)
            self.to_be_checked.setVisible(True)
            self.to_be_labeled.setVisible(True)
        # self.welcome.setText(self.login_name.text() + ",欢迎登录本系统！")

    # 槽函数，动态更新Head_ID下拉框
    def signal_slot(self, ceil_uid):
        self.Head_ID.clear()
        print('信号发射成功', ceil_uid)
        current_id = ceil_uid.replace("U", "")
        if current_id == "1":
            self.submit.setEnabled(False)
            # self.check.setEnabled(False)
            print("warning：U1不可选择head")
        else:
            self.submit.setEnabled(True)
            # self.check.setEnabled(True)
        for i2 in range(int(current_id)):
            if i2 == int(current_id) - 1:
                break
            head_id = "U" + str(i2 + 1)
            self.Head_ID.addItem(head_id)
        if i2:
            self.Head_ID.setCurrentText(head_id)

    # 按键功能绑定
    def btnBind(self):

        # self.import_video.clicked.connect(self.importVideo)  # 导入视频
        # self.import_videos.clicked.connect(self.importVideos)  # 导入文件夹
        self.last.clicked.connect(self.lastLabel)  # 上一个句子
        self.next.clicked.connect(self.nextLabel)  # 下一个句子
        self.jump.clicked.connect(self.jumpLabel)  # 跳转句子
        self.reset.clicked.connect(self.resetLabel)  # 重置标注
        # self.clear.clicked.connect(self.clearLabel)  # 清空标注
        self.same.clicked.connect(self.sameLabel)  # 与上一个句子标注结果相同
        self.submit.clicked.connect(self.submitLabel)  # 提交标注
        self.output_json.clicked.connect(self.outputJson)  # 导出标注
        self.txt_table.cellClicked.connect(self.cellClick)  # 鼠标点击单元格
        self.task_list.itemClicked.connect(self.onClickedListView)  # 鼠标点击列表
        # self.last_task.clicked.connect(self.lastVideo)  # 上一个视频
        # self.next_task.clicked.connect(self.nextVideo)  # 下一个视频
        self.start_time.clicked.connect(self.startWorkTime)  # 开启计时
        self.end_time.clicked.connect(self.endWorkTime)  # 关闭计时
        self.user_picture.clicked.connect(self.userShow)  # 用户界面
        # self.check.clicked.connect(self.submitLabel)  # 提交审核
        self.import_tasks.clicked.connect(self.importTasks)
        self.import_all.clicked.connect(self.importAllTasks)
        self.modify_label.clicked.connect(self.modifyLabel)
        self.modify.clicked.connect(self.modifyLabels)

        self.to_be_labeled.clicked.connect(self.toBeLabeled)  # 未标注完的数据
        self.to_be_checked.clicked.connect(self.toBeChecked)  # 未审核的数据
        self.search_check_result.clicked.connect(self.searchCheckResult)  # 查询审核结果
        self.search_video_name.clicked.connect(self.searchVideoName)  # 查询视频名
        self.finish_task.clicked.connect(self.finishTask)

    def searchVideoName(self):
        self.search_relation_flag=0
        self.task_list.clear()
        if self.method == "审核模式":
            sql = "SELECT video_name, uid, label_1_result, label_2_result, check_result FROM label_result WHERE video_name LIKE %s"
            values = ("%" + self.search_txt.text() + "%")
            cursor.execute(sql, values)
            res = cursor.fetchall()
            if res:
                
                for res_i in res:
                    print(res_i[0])
                    new = res_i[0] + ".mp4"
                    if new not in [self.task_list.item(index).text() for index in range(self.task_list.count())]:
                        # 如果不存在，则添加新行
                        self.task_list.addItem(new)


    def toBeLabeled(self):
        self.search_relation_flag = 0
        self.task_list.clear()
        if self.method == "标注模式":
            print("标注模式下未标完的数据:")

        elif self.method == "审核模式":
            print("审核模式下未标完的数据:")
            sql = "SELECT video_name FROM label_result WHERE uid!=%s and (label_1_result ='' or label_2_result ='')"
            values = 1
            cursor.execute(sql, values)
            res = cursor.fetchall()
            for i in range(len(res)):
                video_name = res[i][0]
                sql = "SELECT assign_name1,assign_name2 FROM video_assign WHERE inst_id=%s"

                values = video_name
                cursor.execute(sql, values)
                res2 = cursor.fetchall()
                new = video_name + ".mp4"
                if new not in [self.task_list.item(index).text() for index in
                               range(self.task_list.count())]:
                    # 如果不存在，则添加新行
                    self.task_list.addItem(new)
                    print(new)

    def toBeChecked(self):
        self.search_relation_flag = 0
        self.task_list.clear()
        if self.method == "审核模式":
            print("审核模式下未审核完的数据:")
            sql = "SELECT video_name FROM label_result WHERE uid!=%s and label_1_result !='' and label_2_result !='' and check_result ='' "
            values = 1
            cursor.execute(sql, values)
            res = cursor.fetchall()

            for i in range(len(res)):
                video_name = res[i][0]
                new = video_name + ".mp4"
                if new not in [self.task_list.item(index).text() for index in
                               range(self.task_list.count())]:
                    # 如果不存在，则添加新行
                    self.task_list.addItem(new)
                    print(new)

    def searchCheckResult(self):
        self.search_relation_flag = 0
        self.task_list.clear()

        if self.method == "审核模式":
            # check_relation = 'Clarification'

            sql = "SELECT video_name, uid, label_1_result, label_2_result, check_result FROM label_result WHERE (check_result LIKE %s) OR (check_result='label_1' AND label_1_result LIKE %s) OR (check_result='label_2' AND label_2_result LIKE %s) OR (check_result='both' AND label_1_result LIKE %s)"
            values = (
                "%" + self.search_txt.text() + "%", "%" + self.search_txt.text() + "%",
                "%" + self.search_txt.text() + "%",
                "%" + self.search_txt.text() + "%")
            cursor.execute(sql, values)
            res = cursor.fetchall()

            if res:
                self.search_relation_flag = 1

            self.search_relation_data = {}
            self.search_relation_head = {}
            print("审核结果中包含", self.search_txt.text(), "的查询结果如下:")

            for i in range(len(res)):
                self.search_relation_video_name = res[i][0]
                self.search_relation_uid = res[i][1]
                label_1_result = res[i][2]
                label_2_result = res[i][3]
                check_result = res[i][4]
                print(label_1_result, label_2_result, check_result)

                if check_result == "label_1" or check_result == "both":
                    match = re.search(r'\d+', label_1_result)
                elif check_result == "label_2":
                    match = re.search(r'\d+', label_2_result)

                else:
                    match = re.search(r'\d+', check_result)
                if match:
                    head = int(match.group())
                    print(head)
                if self.search_relation_video_name not in self.search_relation_head:
                    self.search_relation_head[self.search_relation_video_name] = []  # 创建空列表作为值
                tup = (head, self.search_relation_uid)
                self.search_relation_head[self.search_relation_video_name].append(tup)  # 将值添加到列表中

                if self.search_relation_video_name not in self.search_relation_data:
                    self.search_relation_data[self.search_relation_video_name] = []  # 创建空列表作为值
                self.search_relation_data[self.search_relation_video_name].append(self.search_relation_uid)  # 将值添加到列表中
                new = self.search_relation_video_name + ".mp4"
                if new not in [self.task_list.item(index).text() for index in range(self.task_list.count())]:
                    # 如果不存在，则添加新行
                    self.task_list.addItem(new)
                    print(new, self.search_relation_uid)

            print(self.search_relation_data)
            print(self.search_relation_head)

    def modifyLabels(self):
        print("修改标注")
        self.task_list.clear()
        sql = "SELECT video_name,uid,check_result,check_reason,modify_1_name,modify_1_flag," \
              "modify_2_name, modify_2_flag FROM check_modify " \
              "where (modify_1_name=%s and modify_1_flag=%s) or (modify_2_name=%s and modify_2_flag=%s)"
        values = (self.username, '待修改', self.username, '待修改')
        cursor.execute(sql, values)
        res = cursor.fetchall()
        print(res)
        for i in range(len(res)):
            print(res[i][0])
            new = res[i][0] + ".mp4"
            if new not in [self.task_list.item(index).text() for index in
                           range(self.task_list.count())]:
                # 如果不存在，则添加新行
                self.task_list.addItem(new)

    def modifyLabel(self):
        self.modifyWin = ModifyWin()
        self.modify_signal.connect(self.modifyWin.modify_slot)
        self.modify_signal.emit(self.username, self.method)
        self.modifyWin.show()
        '''
        sql = "SELECT video_name,uid,check_result,check_reason,modify_1_name,modify_1_flag," \
              "modify_2_name, modify_2_flag FROM check_modify " \
              "where modify_1_name=%s or modify_2_name=%s"
        values=(self.username,self.username)
        cursor.execute(sql,values)
        res = cursor.fetchall()
        print(res)
        need_modify_count=0
        for i in range(len(res)):
            modify_1_name = res[i][4]
            modify_1_flag = res[i][5]
            modify_2_name = res[i][6]
            modify_2_flag = res[i][7]
            if (modify_1_name==self.username and modify_1_flag=='待修改') or (modify_2_name==self.username and modify_2_flag=='待修改'):
                need_modify_count += 1
        print(need_modify_count)
        '''

    def finishTask(self):
        print(self.task_list.currentItem().text())
        video_name = self.task_list.currentItem().text()
        sql = "SELECT COUNT(*) FROM label_result WHERE video_name=%s and ((label_1_name=%s and label_1_result!='') OR (label_2_name=%s and label_2_result!='')) "
        values = (video_name, self.login_name.text(), self.login_name.text())
        cursor.execute(sql, values)
        res = cursor.fetchone()
        print(res[0])

        if res[0] == self.txt_table.rowCount() - 1 and self.finish_task.text()!='已完成':  # 除了第一个utt，其他全标了
            # 更新任务分配表的finish flag
            sql="SELECT assign_name1,assign_name2 FROM video_assign_copy WHERE (assign_name1=%s or assign_name2=%s) and inst_id=%s"
            values = (self.login_name.text(), self.login_name.text(),video_name, )
            cursor.execute(sql, values)
            res = cursor.fetchone()
            print(res)
            if res[0]==self.login_name.text():
                sql1 = "UPDATE video_assign_copy SET finish_1_flag = '已完成' WHERE inst_id = %s"
                values = (video_name)
                cursor.execute(sql1, values)
                cnx.commit()
            elif res[1]==self.login_name.text():
                sql2 = "UPDATE video_assign_copy SET finish_2_flag = '已完成' WHERE inst_id = %s"
                values = (video_name)
                cursor.execute(sql2, values)
                cnx.commit()
            # 更新剩余任务表
            sql = "UPDATE surplus_task SET surplus_task= REPLACE(surplus_task, %s, ''),task_count=task_count-1 WHERE name=%s"
            values = (video_name + "|", self.login_name.text())
            cursor.execute(sql, values)
            cnx.commit()
            self.finish_task.setText("已完成")
        else:
            QMessageBox.warning(None, "提示","您还有" + str(self.txt_table.rowCount() - 1 - res[0]) + "个句子没有标注！")

    def importTasks(self):
        '''
        if self.method == "标注模式":
            sql = "SELECT video_name,uid,check_result,check_reason,modify_1_name,modify_1_flag," \
                  "modify_2_name, modify_2_flag FROM check_modify " \
                  "where (modify_1_name=%s and modify_1_flag=%s and appeal_1_reason!=%s) or (modify_2_name=%s and modify_2_flag=%s and appeal_2_reason!=%s)"
            values = (self.username, '待修改', '通过', self.username, '待修改', '通过')
            cursor.execute(sql, values)
            res = cursor.fetchall()
            print(res)
            if res:
                QMessageBox.warning(None, "提示", "请在修改完所有标注错误后，再导入新任务！")
                return
        '''
        self.task_list.clear()
        if self.method == "标注模式":
            # 查询周任务
            sql = "SELECT surplus_task FROM surplus_task WHERE name=%s"
            values = self.login_name.text()
            cursor.execute(sql, values)
            res = cursor.fetchone()
            if res[0]!='':
                task = res[0].split("|")
                for task_i in task:
                    if task_i:
                        item = task_i
                        self.task_list.addItem(item)

            '''
            sql = "SELECT task,week,count FROM task_week where name=%s "
            values = self.login_name.text()
            cursor.execute(sql, values)
            res = cursor.fetchall()
            for i in range(len(res)):
                time = res[i][1]
                start_date = time.split("-")[0]
                end_date = time.split("-")[1]
                print(start_date, end_date)
                start_date2 = start_date.split("/")
                end_date2 = end_date.split("/")
                # 指定起始日期和结束日期
                start_date = date(int(start_date2[0]), int(start_date2[1]), int(start_date2[2]))
                end_date = date(int(end_date2[0]), int(end_date2[1]), int(end_date2[2]))
                # 要判断的日期
                check_date = date.today()
                # 判断日期是否在指定范围内
                if start_date <= check_date <= end_date:
                    print(self.login_name.text(), "本周任务", res[i][0])
                    a = res[i][0].split(",")
                    for i in range(len(a)):
                        if a[i] != "":
                            new = a[i] + ".mp4"
                            if new not in [self.task_list.item(index).text() for index in
                                           range(self.task_list.count())]:
                                # 如果不存在，则添加新行
                                self.task_list.addItem(new)
                else:
                    print(check_date, "is not between the specified dates.")
            '''
        elif self.method == "审核模式":
            # 查询周任务
            sql = "SELECT task,week,count,name FROM task_week"
            cursor.execute(sql)
            res = cursor.fetchall()
            for i in range(len(res)):
                a = res[i][0].split(",")
                for i in range(len(a)):
                    if a[i] != "":
                        new = a[i] + ".mp4"
                        if new not in [self.task_list.item(index).text() for index in
                                       range(self.task_list.count())]:
                            # 如果不存在，则添加新行
                            self.task_list.addItem(new)

                '''
                time = res[i][1]
                print(time)
                start_date = time.split("-")[0]
                end_date = time.split("-")[1]
                print(start_date, end_date)
                start_date2 = start_date.split("/")
                end_date2 = end_date.split("/")
                # 指定起始日期和结束日期
                start_date = date(int(start_date2[0]), int(start_date2[1]), int(start_date2[2]))
                end_date = date(int(end_date2[0]), int(end_date2[1]), int(end_date2[2]))
                # 要判断的日期
                check_date = date.today()
                # 判断日期是否在指定范围内
                if start_date <= check_date <= end_date:
                    print(res[i][0])
                    a = res[i][0].split(",")
                    for i in range(len(a)):
                        if a[i] != "":
                            self.task_list.addItem(a[i] + ".mp4")
                else:
                    print(check_date, "is not between the specified dates.")
                '''

    def importAllTasks(self):
        self.search_relation_flag = 0
        if self.method == "标注模式":
            # 查询周任务
            print(111)
            sql="SELECT inst_id FROM video_assign_copy WHERE assign_name1=%s or assign_name2=%s"
            values = (self.login_name.text(),self.login_name.text())
            cursor.execute(sql, values)
            res = cursor.fetchall()
            for i in res:
                if i[0] not in [self.task_list.item(index).text() for index in
                               range(self.task_list.count())]:
                    self.task_list.addItem(i[0])
            '''
            sql = "SELECT task,week,count FROM task_week where name=%s "
            values = self.login_name.text()
            cursor.execute(sql, values)
            res = cursor.fetchall()
            for i in range(len(res)):
                print(self.login_name.text(), str(res[i][1]), "任务", res[i][0])
                a = res[i][0].split(",")
                for i in range(len(a)):
                    if a[i] != "":
                        new = a[i] + ".mp4"
                        if new not in [self.task_list.item(index).text() for index in
                                       range(self.task_list.count())]:
                            # 如果不存在，则添加新行
                            self.task_list.addItem(new)
            '''

    # 提交审核
    def submitCheck(self):
        if not self.flag:
            return
        '''
        if not self.is_working:
            QMessageBox.warning(None, "提示", "还未开始工作计时！")
            return
        '''

    def userShow(self):
        self.userWin = UserWin()
        self.user_signal.connect(self.userWin.user_slot)
        if self.method == "标注模式":
            self.user_signal.emit(self.username, self.password, self.method, self.hour, self.minute, self.second,
                                  self.label_count)
        elif self.method == "审核模式":
            self.user_signal.emit(self.username, self.password, self.method, self.hour, self.minute, self.second,
                                  self.check_count)
        else:
            print("管理")
        self.userWin.show()

    # 开启工作计时
    def startWorkTime(self):
        self.work_time.setText("00:00:00")
        self.start_work_time = QTime.currentTime()
        self.work_start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # 开始标注的系统时间
        self.work_timer.start(1000)
        self.is_working = True
        self.last_click_time.start()
        self.tip.clear()

        self.ten_min_timer.start(600000)

        query = "INSERT IGNORE INTO per_job (name, date, work_type, work_start_time) VALUES (%s, %s, %s, %s)"
        values = (self.username, date.today(), self.method, self.work_start_time)
        cursor.execute(query, values)
        cnx.commit()

    # 关闭工作计时
    def endWorkTime(self):
        self.work_timer.stop()
        self.is_working = False
        # work_time=self.work_time.text()
        self.tip.setText(
            "您本次工作类型为：" + self.method + ",工作时长为：" + str(self.hour) + "时" + str(
                self.minute) + "分" + str(self.second) + "秒")

        self.work_end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print("work_end_time", self.work_end_time)
        self.time_delta = (datetime.strptime(self.work_end_time, "%Y-%m-%d %H:%M:%S") - \
                           datetime.strptime(self.work_start_time, "%Y-%m-%d %H:%M:%S"))
        print("time_delta", str(self.time_delta))

        if self.method == "标注模式":
            # 执行查询语句
            query = "SELECT COUNT(*) FROM label_result WHERE label_1_name=%s and " \
                    "label_1_time BETWEEN %s AND %s"
            values = (self.username, self.work_start_time, self.work_end_time)
            cursor.execute(query, values)
            result = cursor.fetchone()
            count = result[0]

            query = "SELECT COUNT(*) FROM label_result WHERE label_2_name=%s and " \
                    "label_2_time BETWEEN %s AND %s"
            values = (self.username, self.work_start_time, self.work_end_time)
            cursor.execute(query, values)
            result = cursor.fetchone()
            count = result[0] + count
            print("per count:", count)

            sql = "UPDATE per_job SET per_work_time = %s ,work_end_time = %s ,per_work_amount= %s WHERE name=%s and date=%s and work_type=%s and work_start_time=%s;"
            values = (
                str(self.time_delta), self.work_end_time, count, self.username, date.today(), self.method,
                self.work_start_time)
            cursor.execute(sql, values)
            cnx.commit()

        elif self.method == "审核模式":
            # 执行查询语句
            query = "SELECT COUNT(*) FROM label_result WHERE check_name=%s and " \
                    "check_time BETWEEN %s AND %s"
            values = (self.username, self.work_start_time, self.work_end_time)
            cursor.execute(query, values)
            result = cursor.fetchone()
            count = result[0]

            sql = "UPDATE per_job SET per_work_time = %s ,work_end_time = %s ,per_work_amount= %s WHERE name=%s and date=%s and work_type=%s and work_start_time=%s;"
            values = (
                str(self.time_delta), self.work_end_time, count, self.username, date.today(), self.method,
                self.work_start_time)
            cursor.execute(sql, values)
            cnx.commit()

        # 更新日工时
        sql = "SELECT SUM(TIME_TO_SEC(per_work_time)) AS total_work_time FROM per_job where name=%s and date=%s;"
        values = (self.username, date.today())
        cursor.execute(sql, values)
        result = cursor.fetchone()
        total_work_time = result[0]
        hour = total_work_time // 3600
        minute = (total_work_time // 60) % 60
        second = total_work_time % 60
        day_work_time_str = str(hour) + ":" + str(minute) + ":" + str(second)

        print(date.today(), "total_work_time:", day_work_time_str)

        sql = "UPDATE attendance SET daily_work_time=%s where name=%s and date=%s"
        values = (day_work_time_str, self.username, date.today())
        cursor.execute(sql, values)
        cnx.commit()

    # 更新工作计时
    def updateWorkTime(self):
        self.elapsed_work_time = self.start_work_time.secsTo(QTime.currentTime())
        self.hour = self.elapsed_work_time // 3600
        self.minute = (self.elapsed_work_time // 60) % 60
        self.second = self.elapsed_work_time % 60
        # time_str = self.elapsed_work_time // 3600, (self.elapsed_work_time // 60) % 60, self.elapsed_work_time % 60
        time_str = self.hour, self.minute, self.second

        # self.work_time.display("%02d:%02d:%02d" % time_str)
        self.work_time.setText(str(("%02d:%02d:%02d" % time_str)))

    # 更新系统时间
    def updateSysTime(self):
        sys_date = QDate.currentDate()
        sys_time = QTime.currentTime()
        formatted_datetime = sys_date.toString("yyyy-MM-dd") + " " + sys_time.toString("HH:mm:ss")
        self.system_time.setText(formatted_datetime)

    def format_time(self, milliseconds):
        seconds = milliseconds / 1000
        hours = int(seconds / 3600)
        minutes = int((seconds - hours * 3600) / 60)
        seconds = int(seconds - hours * 3600 - minutes * 60)
        return '{:02d}:{:02d}'.format(minutes, seconds)

    # 跳转播放视频
    def playVideo(self):
        # 读取视频帧

        ret, frame = self.video_capture.read()
        self.media_player.play()
        milliseconds = self.video_capture.get(cv2.CAP_PROP_POS_MSEC)

        self.current_time.setText(self.format_time(milliseconds) + "/" + self.format_time(self.end_ms))
        # 检查是否到达视频的结束时间

        if self.video_capture.get(cv2.CAP_PROP_POS_MSEC) > self.end_ms:
            self.timer.stop()
            self.video_capture.release()
            self.media_player.stop()

        # 将视频帧转换为 QImage
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        # 这种方法下QPixmap.fromImage(image)会报错，导致python崩溃，已弃用
        # image = QImage(frame, frame.shape[1], frame.shape[0], QImage.Format_RGB888)
        # print(QPixmap.fromImage(image))
        height, width, channel = frame.shape
        bytesPerLine = 3 * width
        image = QImage(frame.data, width, height, bytesPerLine,
                       QImage.Format_RGB888)

        # 在 QLabel 中自适应显示 QImage
        self.video.setPixmap(
            (QPixmap.fromImage(image)).scaled(self.video.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    # 鼠标点击表格单元格事件
    def cellClick(self):
        for i in self.txt_table.selectedItems():
            self.check_reason.clear()
            print(i.row() + 1, i.column() + 1, i.text())
            ceil_uid = self.txt_table.item(i.row(), 0)
            self.current_utterance.setText(ceil_uid.text())
            self.table_row = i.row()
            self.table_col = i.column()

            # 方法一：跳转播放选中时间段的视频
            # 加载视频文件
            self.video_capture = cv2.VideoCapture(self.video_name.text())

            # 获取起止毫秒
            if self.method == "标注模式":
                hours, minutes, seconds, milliseconds = map(int,
                                                            self.txt_table.item(self.table_row, 3).text().split(":"))
                total_milliseconds = (((hours * 60 + minutes) * 60) + seconds) * 1000 + milliseconds
                self.start_ms = total_milliseconds

                hours, minutes, seconds, milliseconds = map(int,
                                                            self.txt_table.item(self.table_row, 4).text().split(":"))
                total_milliseconds = (((hours * 60 + minutes) * 60) + seconds) * 1000 + milliseconds
                self.end_ms = total_milliseconds
            elif self.method == "审核模式":

                hours, minutes, seconds, milliseconds = map(int,
                                                            self.txt_table.item(self.table_row, 3).text().split(":"))
                total_milliseconds = (((hours * 60 + minutes) * 60) + seconds) * 1000 + milliseconds
                self.start_ms = total_milliseconds

                hours, minutes, seconds, milliseconds = map(int,
                                                            self.txt_table.item(self.table_row, 4).text().split(":"))
                total_milliseconds = (((hours * 60 + minutes) * 60) + seconds) * 1000 + milliseconds
                self.end_ms = total_milliseconds

                sql = "SELECT check_reason FROM check_modify where video_name=%s and uid=%s"
                values = (self.videoName, int(ceil_uid.text().replace("U", "")))
                cursor.execute(sql, values)
                res = cursor.fetchone()

                if res is not None:
                    self.check_reason.setText(res[0])
                else:
                    self.check_reason.setText("")

            # 跳转到视频的开始时间
            self.fps = self.video_capture.get(cv2.CAP_PROP_FPS)
            print("fps ", self.fps)
            start_frame = int(self.start_ms / 1000 * self.fps)
            self.video_capture.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
            print("start_frame ", start_frame)
            self.media_player.setPosition(self.start_ms)

            # 开始定时器
            self.timer.start(int(1000 / self.fps))

            # 发送信号，更新当前选中的句子编号
            self.my_signal.emit(ceil_uid.text())
            print("更新当前选中的句子编号")

        '''
            #方法二：跳转显示视频的某一帧图片
            #加载视频文件
            cap = cv2.VideoCapture(self.video_name.text())
            # 将视频跳转到n毫秒处
            hours, minutes, seconds, milliseconds = map(int, self.txt_table.item(self.row, 3).text().split(":"))
            total_milliseconds = (((hours * 60 + minutes) * 60) + seconds) * 1000 + milliseconds
            print(total_milliseconds)
            position = total_milliseconds
            cap.set(cv2.CAP_PROP_POS_MSEC, position)            
 
            ret, image = cap.read()
            if ret:
                if len(image.shape) == 3:
                    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                    vedio_img = QImage(image.data, image.shape[1], image.shape[0], QImage.Format_RGB888)
                elif len(image.shape) == 1:
                    vedio_img = QImage(image.data, image.shape[1], image.shape[0], QImage.Format_Indexed8)
                else:
                    vedio_img = QImage(image.data, image.shape[1], image.shape[0], QImage.Format_RGB888)

                self.video.setPixmap(QPixmap(vedio_img))
                self.video.setScaledContents(True)  # 自适应窗口
        '''

    # 鼠标点击列表事件
    def onClickedListView(self, item):
        print("Item clicked:", item.text())
        self.folder = os.path.dirname((os.path.abspath(__file__))) + "/data/" + item.text().split("_")[0]

        if self.search_relation_flag == 1:
            print("search_relation_flag == 1")
            self.videoInfomation(self.folder + "/" + item.text(), 1, self.search_relation_data)
        else:
            print("search_relation_flag == 0")
            self.videoInfomation(self.folder + "/" + item.text(), 0, self.search_relation_data)
        print(self.folder + "/" + item.text())

        if self.method=="标注模式":
            sql= "SELECT assign_name1,assign_name2,finish_1_flag,finish_2_flag FROM video_assign_copy WHERE inst_id=%s and (assign_name1=%s or assign_name2=%s)"
            values=(self.task_list.currentItem().text(),self.login_name.text(),self.login_name.text())
            cursor.execute(sql,values)
            res=cursor.fetchone()
            if res[0] == self.login_name.text():
                if res[2]!='':
                    self.finish_task.setText(res[2])
                else:
                    self.finish_task.setText('待完成')
            elif res[1] == self.login_name.text():
                if res[3]!='':
                    self.finish_task.setText(res[3])
                else:
                    self.finish_task.setText('待完成')

    # 计算视频时长
    def video_duration(self, filename):
        cap = cv2.VideoCapture(filename)
        if cap.isOpened():
            rate = cap.get(5)
            frame_num = cap.get(7)
            duration = frame_num / rate
            return duration
        return -1

    # 播放视频，显示视频信息，包括视频时长、txt、speaker、句子总数，并创建标注文件
    def videoInfomation(self, filePath, search_relation_flag, search_relation_data):
        if ".mp4" not in filePath:
            filePath=filePath+".mp4"
        # 清空
        print("search_relation_flag:", search_relation_flag)
        print("search_relation_data:", search_relation_data)
        self.Head_ID.clear()
        self.txt_table.setRowCount(0)
        self.video.clear()
        self.flag = 1
        self.video_name.setText(filePath)

        print("video_filePath:", self.video_name.text())

        # 设置QMediaPlayer的媒体源，并开始播放视频
        file_url = QUrl.fromLocalFile(filePath)
        self.media_player.setMedia(QMediaContent(file_url))
        self.media_player.play()

        # 显示视频时长
        duration = self.video_duration(filePath)
        duration = int(duration + 0.5)
        m, s = divmod(duration, 60)
        strTime = '%02d:%02d' % (m, s)
        self.video_time.setText(strTime)
        print("duration:", duration)

        # 获取视频名、节目名
        videoName = os.path.basename(filePath).replace(".mp4", "")
        TVName = re.split(r"_\d", videoName)[0]
        print("videoName:", videoName)
        print("TVName:", TVName)
        self.videoName = videoName
        self.TVName = TVName

        if self.method == "标注模式":
            if not os.path.exists("results\\txt\\" + TVName):
                os.mkdir("results\\txt\\" + TVName)
            if not os.path.exists("results\\json\\" + TVName):
                os.mkdir("results\\json\\" + TVName)

            self.path_txt = "results\\txt\\" + TVName + "\\" + videoName + ".txt"
            self.path_json = "results\\json\\" + TVName + "\\" + videoName + ".json"

            # 读取json数据
            f = open("data/test.json", "r", encoding="utf-8")
            data = json.load(f)
            flag = 0
            self.json = ""
            for index, key in enumerate(data.keys()):
                print(key)
                if key == TVName:
                    flag = 1
                    self.json = "data/test.json"
                    break
                if index + 1 == len(data.keys()):
                    flag = 0

            if flag == 0:
                f = open("data/train.json", "r", encoding="utf-8")
                data = json.load(f)
                flag = 0
                for index, key in enumerate(data.keys()):
                    print(key)
                    if key == TVName:
                        flag = 1
                        self.json = "data/train.json"
                        break
                    if index + 1 == len(data.keys()):
                        flag = 0

            if flag == 0:
                f = open("data/val.json", "r", encoding="utf-8")
                data = json.load(f)
                flag = 0
                for index, key in enumerate(data.keys()):
                    print(key)
                    if key == TVName:
                        flag = 1
                        self.json = "data/val.json"
                        break
                    if index + 1 == len(data.keys()):
                        flag = 0

            if flag == 1:
                # 读取json数据
                f = open(self.json, "r", encoding="utf-8")
                data = json.load(f)
                data_1 = data[TVName][videoName]
                self.result = data_1
                print(data_1)

                # 显示说话人A、B
                speakerA_Name = data_1["SpeakerInfo"]["A"]["Name"]
                speakerB_Name = data_1["SpeakerInfo"]["B"]["Name"]
                print(speakerA_Name)
                print(speakerB_Name)
                self.speakerA.setText(speakerA_Name)
                self.speakerB.setText(speakerB_Name)

                # 显示对话文本
                dialog = data_1["Dialog"]
                i = 0
                i2 = 0
                for dialog_key in dialog.keys():
                    i = i + 1
                    print(dialog_key)
                    dialog_i = dialog[dialog_key]
                    print(dialog_i["Text"])
                    id = str(i)
                    Uid = "U" + id

                    # TableWidget
                    self.txt_table.setColumnCount(9)
                    self.txt_table.resizeColumnsToContents()
                    # 设置列名
                    column_names = ["Uid", "Speaker", "Txt", "StartTime", "EndTime", "Head_id", "Relation",
                                    "Label_time",
                                    "Check_result"]
                    self.txt_table.setHorizontalHeaderLabels(column_names)

                    row_new = self.txt_table.rowCount()  # 返回当前行数(尾部)
                    print("row:", row_new)
                    self.txt_table.insertRow(row_new)

                    item1 = QTableWidgetItem(Uid)

                    self.txt_table.setItem(row_new, 0, item1)
                    self.txt_table.setItem(row_new, 1, QTableWidgetItem(dialog_i['Speaker']))
                    self.txt_table.setItem(row_new, 2, QTableWidgetItem(dialog_i['Text']))
                    self.txt_table.setItem(row_new, 3, QTableWidgetItem(dialog_i['StartTime']))
                    self.txt_table.setItem(row_new, 4, QTableWidgetItem(dialog_i['EndTime']))

                    query = "INSERT IGNORE INTO label_result (tv_name, video_name,uid,speaker,txt,start_time,end_time) VALUES (%s, %s, %s,%s,%s,%s,%s) "
                    values = (
                        TVName, videoName, i, dialog_i['Speaker'], dialog_i['Text'], dialog_i['StartTime'],
                        dialog_i['EndTime'])
                    cursor.execute(query, values)

                    query = "SELECT label_1_name,label_2_name,label_1_result,label_2_result,label_1_time,label_2_time FROM label_result where tv_name=%s and video_name=%s and uid=%s"
                    values = (TVName, videoName, i)
                    cursor.execute(query, values)
                    res = cursor.fetchone()

                    if not res[0]:
                        self.txt_table.setItem(row_new, 5, QTableWidgetItem('-'))
                        self.txt_table.setItem(row_new, 6, QTableWidgetItem('-'))
                        self.txt_table.setItem(row_new, 7, QTableWidgetItem('-'))
                    elif self.login_name.text() == res[0]:  # 是label1标注员
                        if res[2]:
                            label = res[2]
                            start_index = label.index("(") + 1  # 获取左括号后的索引位置
                            end_index = label.index(")")  # 获取右括号的索引位置
                            extracted_data_type = label[start_index:end_index].split(",")
                            self.txt_table.setItem(row_new, 5, QTableWidgetItem(extracted_data_type[0]))
                            self.txt_table.setItem(row_new, 6, QTableWidgetItem(extracted_data_type[1]))
                            self.txt_table.setItem(row_new, 7, QTableWidgetItem(str(res[4])))
                        else:
                            self.txt_table.setItem(row_new, 5, QTableWidgetItem('-'))
                            self.txt_table.setItem(row_new, 6, QTableWidgetItem('-'))
                            self.txt_table.setItem(row_new, 7, QTableWidgetItem('-'))
                    elif self.login_name.text() == res[1]:  # 是label2标注员
                        if res[3]:
                            label = res[3]
                            start_index = label.index("(") + 1  # 获取左括号后的索引位置
                            end_index = label.index(")")  # 获取右括号的索引位置
                            extracted_data_type = label[start_index:end_index].split(",")
                            self.txt_table.setItem(row_new, 5, QTableWidgetItem(extracted_data_type[0]))
                            self.txt_table.setItem(row_new, 6, QTableWidgetItem(extracted_data_type[1]))
                            self.txt_table.setItem(row_new, 7, QTableWidgetItem(str(res[5])))
                        else:
                            self.txt_table.setItem(row_new, 5, QTableWidgetItem('-'))
                            self.txt_table.setItem(row_new, 6, QTableWidgetItem('-'))
                            self.txt_table.setItem(row_new, 7, QTableWidgetItem('-'))
                    else:
                        self.txt_table.setItem(row_new, 5, QTableWidgetItem('-'))
                        self.txt_table.setItem(row_new, 6, QTableWidgetItem('-'))
                        self.txt_table.setItem(row_new, 7, QTableWidgetItem('-'))

                    query = "SELECT check_result,label_1_name,label_2_name,label_1_result,label_2_result FROM label_result where tv_name=%s and video_name=%s and uid=%s"
                    values = (TVName, videoName, i)
                    cursor.execute(query, values)
                    res = cursor.fetchone()

                    if not res[0]:
                        self.txt_table.setItem(row_new, 8, QTableWidgetItem('-'))
                    elif res[0] == 'both':
                        self.txt_table.setItem(row_new, 8, QTableWidgetItem('通过'))
                    elif res[0] == 'label_1':
                        if self.login_name.text() == res[1]:  # 登陆人为标注员1，审核为label_1，正确
                            self.txt_table.setItem(row_new, 8, QTableWidgetItem('通过'))
                        elif self.login_name.text() == res[2]:  # 登陆人为标注员2，审核为label_1，不正确
                            self.txt_table.setItem(row_new, 8, QTableWidgetItem('未通过，建议标注为：' + res[3]))
                        else:
                            self.txt_table.setItem(row_new, 8,
                                                   QTableWidgetItem('您不是此数据的标注员，无法查看审核结果'))
                    elif res[0] == 'label_2':
                        if self.login_name.text() == res[2]:  # 登陆人为标注员2，审核为label_2，正确
                            self.txt_table.setItem(row_new, 8, QTableWidgetItem('通过'))
                        elif self.login_name.text() == res[1]:  # 登陆人为标注员1，审核为label_2，不正确
                            self.txt_table.setItem(row_new, 8, QTableWidgetItem('未通过，建议标注为：' + res[4]))
                        else:
                            self.txt_table.setItem(row_new, 8,
                                                   QTableWidgetItem('您不是此数据的标注员，无法查看审核结果'))
                    elif res[0] != 'both' and res[0] != 'label_1' and res[0] != 'label_2':
                        if self.login_name.text() == res[1] or self.login_name.text() == res[2]:
                            self.txt_table.setItem(row_new, 8, QTableWidgetItem('未通过，建议标注为：' + res[0]))
                        else:
                            self.txt_table.setItem(row_new, 8,
                                                   QTableWidgetItem('您不是此数据的标注员，无法查看审核结果'))

            # 显示句子总数
            total_utt = i
            print("total_utt:", total_utt)
            self.total_utterance.setText(str(total_utt))

            # 更新标注文件
            self.updateLabel_txt()

            if os.path.exists(self.path_json):
                self.updateLabel_json()
            else:
                self.initLabel_json()
                self.updateLabel_json()

        elif self.method == "审核模式":

            if not os.path.exists("checks\\txt\\" + TVName):
                os.mkdir("checks\\txt\\" + TVName)
            if not os.path.exists("checks\\json\\" + TVName):
                os.mkdir("checks\\json\\" + TVName)

            self.path_txt = "checks\\txt\\" + TVName + "\\" + videoName + ".txt"
            self.path_json = "checks\\json\\" + TVName + "\\" + videoName + ".json"

            # 读取json数据
            f = open("data/test.json", "r", encoding="utf-8")
            data = json.load(f)
            flag = 0
            self.json = ""
            for index, key in enumerate(data.keys()):
                print(key)
                if key == TVName:
                    flag = 1
                    self.json = "data/test.json"
                    break
                if index + 1 == len(data.keys()):
                    flag = 0

            if flag == 0:
                f = open("data/train.json", "r", encoding="utf-8")
                data = json.load(f)
                flag = 0
                for index, key in enumerate(data.keys()):
                    print(key)
                    if key == TVName:
                        flag = 1
                        self.json = "data/train.json"
                        break
                    if index + 1 == len(data.keys()):
                        flag = 0

            if flag == 0:
                f = open("data/val.json", "r", encoding="utf-8")
                data = json.load(f)
                flag = 0
                for index, key in enumerate(data.keys()):
                    print(key)
                    if key == TVName:
                        flag = 1
                        self.json = "data/val.json"
                        break
                    if index + 1 == len(data.keys()):
                        flag = 0

            if flag == 1:
                # 读取json数据
                f = open(self.json, "r", encoding="utf-8")
                data = json.load(f)
                data_1 = data[TVName][videoName]
                self.result = data_1
                print(data_1)

                # 显示说话人A、B
                speakerA_Name = data_1["SpeakerInfo"]["A"]["Name"]
                speakerB_Name = data_1["SpeakerInfo"]["B"]["Name"]
                print(speakerA_Name)
                print(speakerB_Name)
                self.speakerA.setText(speakerA_Name)
                self.speakerB.setText(speakerB_Name)

                query = "SELECT * FROM label_result where tv_name=%s and video_name=%s"
                values = (TVName, videoName)
                cursor.execute(query, values)
                res = cursor.fetchall()
                i2 = 0
                i = 0
                for row in res:
                    i = i + 1
                    self.txt_table.setColumnCount(9)
                    self.txt_table.resizeColumnsToContents()
                    column_names = ["Uid", "Speaker", "Txt", "StartTime", "EndTime", "Label_1", "Label_2",
                                    "Check_result",
                                    "Check_time"]
                    self.txt_table.setHorizontalHeaderLabels(column_names)
                    # if row[5] and row[8]:
                    print(row[5], row[8])
                    # TableWidget
                    Uid = "U" + str(row[2])

                    row_new = self.txt_table.rowCount()  # 返回当前行数(尾部)
                    print("row" + str(row_new), Uid, row[3], row[4], row[5], row[8])
                    self.txt_table.insertRow(row_new)

                    item1 = QTableWidgetItem(Uid)
                    item2 = QTableWidgetItem(row[3])
                    item3 = QTableWidgetItem(row[4])
                    item4 = QTableWidgetItem(row[5])
                    item5 = QTableWidgetItem(row[6])
                    item6 = QTableWidgetItem(row[7])
                    item7 = QTableWidgetItem(row[10])
                    color_flag = 0
                    # 添加背景色

                    if search_relation_flag == 1:
                        if videoName in search_relation_data:
                            print(search_relation_data[videoName])
                            if i in search_relation_data[videoName]:
                                color_flag = 1

                        if videoName in self.search_relation_head:
                            for i2 in self.search_relation_head[videoName]:
                                if i == i2[0]:
                                    color_flag = 2

                    if color_flag == 1:
                        item1.setBackground(QColor(255, 165, 0))
                        item2.setBackground(QColor(255, 165, 0))
                        item3.setBackground(QColor(255, 165, 0))
                        item4.setBackground(QColor(255, 165, 0))
                        item5.setBackground(QColor(255, 165, 0))
                        item6.setBackground(QColor(255, 165, 0))
                        item7.setBackground(QColor(255, 165, 0))
                    if color_flag == 2:
                        item1.setBackground(QColor(173, 216, 230))
                        item2.setBackground(QColor(173, 216, 230))
                        item3.setBackground(QColor(173, 216, 230))
                        item4.setBackground(QColor(173, 216, 230))
                        item5.setBackground(QColor(173, 216, 230))
                        item6.setBackground(QColor(173, 216, 230))
                        item7.setBackground(QColor(173, 216, 230))

                    self.txt_table.setItem(row_new, 0, item1)
                    self.txt_table.setItem(row_new, 1, item2)  # speaker
                    self.txt_table.setItem(row_new, 2, item3)  # txt
                    self.txt_table.setItem(row_new, 3, item4)
                    self.txt_table.setItem(row_new, 4, item5)
                    self.txt_table.setItem(row_new, 5, item6)  # label1
                    self.txt_table.setItem(row_new, 6, item7)  # label2

                    sql = "SELECT check_time,check_result,check_name FROM label_result where tv_name=%s and video_name=%s and uid=%s"
                    values = (TVName, videoName, row[2])
                    cursor.execute(sql, values)
                    res = cursor.fetchone()
                    print("check_time", res[0])

                    if res[1]:
                        item8 = QTableWidgetItem(res[1])
                        self.txt_table.setItem(row_new, 7, item8)  # check result
                        if color_flag == 1:
                            item8.setBackground(QColor(255, 165, 0))
                        if color_flag == 2:
                            item8.setBackground(QColor(173, 216, 230))
                        # self.txt_table.setItem(row_new, 8, QTableWidgetItem(check_res[0]))  # check reason
                        self.txt_table.setItem(row_new, 8, QTableWidgetItem(str(res[0])))  # check time

                    else:
                        self.txt_table.setItem(row_new, 7, QTableWidgetItem('-'))
                        self.txt_table.setItem(row_new, 8, QTableWidgetItem('-'))
                        # self.txt_table.setItem(row_new, 9, QTableWidgetItem('-'))

                    # 显示句子总数
                    total_utt = self.txt_table.rowCount()
                    print("total_utt:", total_utt)
                    self.total_utterance.setText(str(total_utt))

                    # 更新标注文件
                    self.updateLabel_txt()

                    if os.path.exists(self.path_json):
                        self.updateLabel_json()
                    else:
                        self.initLabel_json()

    # 导入视频
    def importVideo(self):
        # 打开文件
        filePath, fileType = QFileDialog.getOpenFileName(self, "打开文件", "", "All Files(*)")
        if filePath == '':
            return

        self.folder = os.path.dirname(os.path.dirname(filePath))
        self.folder_dirname = os.path.basename(self.folder)
        print("folder:", self.folder, self.folder_dirname)
        self.videoInfomation(filePath, 0, self.search_relation_data)

        new_item_text = os.path.basename(filePath)
        if new_item_text not in [self.task_list.item(index).text() for index in range(self.task_list.count())]:
            # 如果不存在，则添加新行
            self.task_list.addItem(new_item_text)
        else:
            print("already in task_list!")
        # self.task_list.setCurrentRow(0)

        for i in range(self.task_list.count()):
            item = self.task_list.item(i)
            if item.text() == os.path.basename(filePath):
                # 如果找到了目标内容，将当前行设置为该行
                self.task_list.setCurrentRow(i)
                break

    # 导入文件夹
    def importVideos(self):
        self.task_list.clear()
        folderPath = QFileDialog.getExistingDirectory(self, "Select Directory")
        if folderPath == '':
            return
        print(folderPath)
        self.folder = folderPath
        self.folder_dirname = os.path.basename(os.path.dirname(self.folder))
        print("folder:", self.folder_dirname)
        a = []
        fileCount = 0
        for fileName in os.listdir(folderPath):
            if fileName.endswith(".mp4"):
                fileCount += 1
                filePath = os.path.join(folderPath, fileName)
                new_item_text = os.path.basename(filePath)
                # print(fileName)
                fileName1 = fileName.replace(".mp4", "")
                fileName2 = fileName1.split("_")
                # print(fileName2[1])
                a.append(int(fileName2[1]))
                a.sort()
                '''
                if new_item_text not in [self.task_list.item(index).text() for index in range(self.task_list.count())]:
                # 如果不存在，则添加新行
                    self.task_list.addItem(new_item_text)
                '''

        for i in range(len(a)):
            new_item_text = os.path.basename(folderPath) + "_" + str(a[i]) + ".mp4"
            self.task_list.addItem(new_item_text)

    # 重置标注
    def resetLabel(self):
        if not self.flag:
            return

        video_name = (os.path.basename(self.path_txt)).replace(".txt", "")
        tv_name = (video_name.split("_"))[0]
        uid = self.current_utterance.text().replace("U", "")
        if self.method == "标注模式":
            self.txt_table.setItem(self.table_row, 5, QTableWidgetItem('-'))
            self.txt_table.setItem(self.table_row, 6, QTableWidgetItem('-'))
            self.txt_table.setItem(self.table_row, 7, QTableWidgetItem('-'))

            self.updateLabel_txt()
            self.updateLabel_json()

            sql = "SELECT label_1_name, label_2_name FROM label_result where tv_name=%s and video_name=%s and uid=%s"
            values = (tv_name, video_name, int(uid))
            cursor.execute(sql, values)
            res = cursor.fetchone()
            print("label_1_name, label_2_name", res[0], res[1])
            if self.username == res[0]:
                sql = "UPDATE label_result SET label_1_result=null,label_1_time=null where tv_name=%s and video_name=%s and uid=%s"
                values = (tv_name, video_name, int(uid))
                cursor.execute(sql, values)
                cnx.commit()

            if self.username == res[1]:
                sql = "UPDATE label_result SET label_2_result=null,label_2_time=null where tv_name=%s and video_name=%s and uid=%s"
                values = (tv_name, video_name, int(uid))
                cursor.execute(sql, values)
                cnx.commit()

        elif self.method == "审核模式":
            self.txt_table.setItem(self.table_row, 7, QTableWidgetItem('-'))
            self.txt_table.setItem(self.table_row, 8, QTableWidgetItem('-'))

            self.updateLabel_txt()
            self.updateLabel_json()

            sql = "SELECT check_name,label_1_name,label_2_name FROM label_result where tv_name=%s and video_name=%s and uid=%s"
            values = (tv_name, video_name, int(uid))
            cursor.execute(sql, values)
            res = cursor.fetchone()
            print("check_name", res[0])
            if self.username == res[0]:
                sql = "UPDATE label_result SET check_result=null,check_time=null where tv_name=%s and video_name=%s and uid=%s"
                values = (tv_name, video_name, int(uid))
                cursor.execute(sql, values)
                cnx.commit()

                # 更新user表
                sql = "UPDATE user SET been_checked_amount=been_checked_amount-1 where name=%s"
                values = res[1]
                cursor.execute(sql, values)
                cnx.commit()

                sql = "UPDATE user SET been_checked_amount=been_checked_amount-1 where name=%s"
                values = res[2]
                cursor.execute(sql, values)
                cnx.commit()

    '''
    # 清空标注
    def clearLabel(self):
        if not self.flag:
            return
        for row in range(self.txt_table.rowCount()):
            self.txt_table.setItem(row, 5, QTableWidgetItem('-'))
            self.txt_table.setItem(row, 6, QTableWidgetItem('-'))
            self.txt_table.setItem(row, 7, QTableWidgetItem('-'))
        self.updateLabel_txt()
        self.updateLabel_json()
    '''

    # 同上句标注
    def sameLabel(self):
        if not self.flag:
            return
        same_label_headID = self.txt_table.item(self.table_row - 1, 5).text()
        self.txt_table.setItem(self.table_row, 5, QTableWidgetItem(same_label_headID))
        same_label_relation = self.txt_table.item(self.table_row - 1, 6).text()
        self.txt_table.setItem(self.table_row, 6, QTableWidgetItem(same_label_relation))

        self.Head_ID.setCurrentText(same_label_headID)
        self.relation.setCurrentText(same_label_relation)

        print("same label:", self.table_row, same_label_headID, same_label_relation)

    # 提交标注
    def submitLabel(self):
        if not self.flag:
            return
        if not self.is_working:
            QMessageBox.warning(None, "提示", "还未开始工作计时！")
            return
        if self.is_working:
            if self.method == "审核模式":
                label_1 = self.txt_table.item(self.table_row, 5).text()
                label_2 = self.txt_table.item(self.table_row, 6).text()
                print("label_1,label_2:", label_1, label_2)
                if self.check_result.currentText() == 'both':
                    if label_1 != label_2:
                        QMessageBox.warning(None, "提示", "两个标注不同，但审核为both，请检查您的审核结果！")
                        return
                if self.check_result.currentText() == 'other':
                    check_result = "(" + self.Head_ID.currentText() + "," + self.relation.currentText() + ")"
                    if check_result == label_1:
                        QMessageBox.warning(None, "提示", "新标注与label_1相同，请检查您的审核结果！")
                        return
                    if check_result == label_2:
                        QMessageBox.warning(None, "提示", "新标注与label_2相同，请检查您的审核结果！")
                        return
            current_time = QElapsedTimer()
            current_time.start()
            self.elapsed_milliseconds = int(self.last_click_time.elapsed() / 1000)  # 获取与上次点击的时间间隔（秒）
            self.elapsed_minute = (self.elapsed_milliseconds // 60) % 60
            self.elapsed_second = self.elapsed_milliseconds % 60
            self.last_click_time = current_time

            self.ten_min_timer.start(600000)  # 开启鼠标点击计时器

            print(f"时间间隔：{self.elapsed_minute}分钟{self.elapsed_second}秒")

            print("提交时间：", self.system_time.text())
            print("提交人：", self.username)

            data_result = "(" + self.Head_ID.currentText() + "," + self.relation.currentText() + ")"
            print("path_txt:", self.path_txt)
            video_name = (os.path.basename(self.path_txt)).replace(".txt", "")
            tv_name = (video_name.split("_"))[0]
            print(video_name, tv_name)

            # 更新per_job表
            self.work_end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print("work_end_time", self.work_end_time)
            self.time_delta = (datetime.strptime(self.work_end_time, "%Y-%m-%d %H:%M:%S") - \
                               datetime.strptime(self.work_start_time, "%Y-%m-%d %H:%M:%S"))
            print("time_delta", str(self.time_delta))

            # 更新表格
            if self.method == "标注模式":
                self.txt_table.setItem(self.table_row, 5, QTableWidgetItem(self.Head_ID.currentText()))
                self.txt_table.setItem(self.table_row, 6, QTableWidgetItem(self.relation.currentText()))
                self.txt_table.setItem(self.table_row, 7, QTableWidgetItem(self.system_time.text()))

                # 更新label_result表

                query = "SELECT label_1_name FROM label_result where tv_name=%s and video_name=%s and uid=%s"
                values = (tv_name, video_name, self.table_row + 1)
                cursor.execute(query, values)
                res = cursor.fetchall()
                print(res[0])
                if res[0][0]:  # 已有标注1
                    print("label_1_name is not null")
                    if res[0][0] == self.username:  # 标注1是当前标注人员标注，则更新标注1
                        query = "UPDATE label_result SET label_1_name = %s ,label_1_result = %s,label_1_time =%s " \
                                "where tv_name=%s and video_name=%s and uid=%s "
                        values = (
                            self.username, data_result, self.work_end_time, tv_name, video_name, self.table_row + 1)
                        cursor.execute(query, values)
                        cnx.commit()
                        # 更新check_modify表
                        if self.txt_table.item(self.table_row, 8).text() != "通过" and self.txt_table.item(
                                self.table_row, 8).text().replace("未通过，建议标注为：", "") == data_result:
                            print("已修改")
                            print(data_result)
                            sql = "UPDATE check_modify SET modify_1_flag = %s where video_name=%s and uid=%s "
                            values = ("已修改", video_name, self.table_row + 1)
                            cursor.execute(sql, values)
                            cnx.commit()

                    else:  # 标注1非当前标注人员标注，则将新标注存入标注2
                        query = "UPDATE label_result SET label_2_name = %s ,label_2_result = %s,label_2_time =%s " \
                                "where tv_name=%s and video_name=%s and uid=%s "
                        values = (
                            self.username, data_result, self.work_end_time, tv_name, video_name, self.table_row + 1)
                        cursor.execute(query, values)
                        cnx.commit()
                        # 更新check_modify表
                        if self.txt_table.item(self.table_row, 8).text() != "通过" and self.txt_table.item(
                                self.table_row, 8).text().replace("未通过，建议标注为：", "") == data_result:
                            print("已修改")
                            print(data_result)
                            sql = "UPDATE check_modify SET modify_2_flag = %s where video_name=%s and uid=%s "
                            values = ("已修改", video_name, self.table_row + 1)
                            cursor.execute(sql, values)
                            cnx.commit()


                else:  # 没有标注1，则将标注结果存入标注1
                    print("label_1_name is null")
                    query = "UPDATE label_result SET label_1_name = %s ,label_1_result = %s,label_1_time =%s " \
                            "where tv_name=%s and video_name=%s and uid=%s "
                    values = (self.username, data_result, self.work_end_time, tv_name, video_name, self.table_row + 1)
                    cursor.execute(query, values)
                    cnx.commit()

                # 执行查询语句
                query = "SELECT COUNT(*) FROM label_result WHERE label_1_name=%s and " \
                        "label_1_time BETWEEN %s AND %s"
                values = (self.username, self.work_start_time, self.work_end_time)
                cursor.execute(query, values)

                # 获取查询结果
                result = cursor.fetchone()
                count = result[0]

                query = "SELECT COUNT(*) FROM label_result WHERE label_2_name=%s and " \
                        "label_2_time BETWEEN %s AND %s"
                values = (self.username, self.work_start_time, self.work_end_time)
                cursor.execute(query, values)
                result = cursor.fetchone()
                count = result[0] + count

                print("per count:", count)

                sql = "UPDATE per_job SET per_work_time = %s ,work_end_time = %s ,per_work_amount= %s WHERE name=%s and date=%s and work_type=%s and work_start_time=%s;"
                values = (
                    str(self.time_delta), self.work_end_time, count, self.username, date.today(), self.method,
                    self.work_start_time)
                cursor.execute(sql, values)
                cnx.commit()

            elif self.method == "审核模式":
                # if self.result_frame.isEnabled():
                ii = int(self.current_utterance.text().replace('U', ''))
                print("Uid", ii)

                # 设置不能审核自己标注的数据
                query = "SELECT label_1_name,label_2_name FROM label_result WHERE tv_name=%s and video_name=%s and uid=%s "
                values = (tv_name, video_name, ii)
                cursor.execute(query, values)
                res = cursor.fetchone()
                label_1_name = res[0]
                label_2_name = res[1]

                '''
                if self.login_name.text() == res[0] or self.login_name.text() == res[1]:
                    QMessageBox.warning(None, "提示", "您不能审核自己标注的数据！")
                    return
                '''

                if self.relation.isEnabled():
                    other = "(" + self.Head_ID.currentText() + "," + self.relation.currentText() + ")"
                    print("other:", other)
                    self.txt_table.setItem(self.table_row, 7, QTableWidgetItem(other))
                    self.txt_table.setItem(self.table_row, 8, QTableWidgetItem(self.system_time.text()))
                else:
                    self.txt_table.setItem(self.table_row, 7, QTableWidgetItem(self.check_result.currentText()))
                    self.txt_table.setItem(self.table_row, 8, QTableWidgetItem(self.system_time.text()))

                # 更新审核结果
                sql = "UPDATE label_result SET check_name = %s ,check_result = %s,check_time =%s " \
                      "where tv_name=%s and video_name=%s and uid=%s "
                values = (self.username,
                          self.txt_table.item(self.table_row, 7).text(),
                          self.system_time.text(), tv_name, video_name, ii)
                cursor.execute(sql, values)
                cnx.commit()

                # 更新check_modify表
                sql = "SELECT video_name,uid,check_result,label_1_name,label_2_name,check_name,label_1_result,label_2_result FROM label_result where video_name=%s and uid=%s"
                values = (video_name, ii)
                cursor.execute(sql, values)
                res = cursor.fetchone()
                print(res)
                video_name = res[0]
                uid = res[1]
                check_result = res[2]
                label_1_name = res[3]
                label_2_name = res[4]
                check_name = res[5]
                modify_1_result = res[6]
                modify_2_result = res[7]

                if check_result == 'label_1':
                    modify_1_flag = '无需修改'
                    modify_2_flag = '待修改'
                elif check_result == 'label_2':
                    modify_1_flag = '待修改'
                    modify_2_flag = '无需修改'
                else:
                    modify_1_flag = '待修改'
                    modify_2_flag = '待修改'
                sql = "SELECT * FROM check_modify where video_name=%s and uid=%s"
                values = (video_name, uid)
                cursor.execute(sql, values)
                check_res = cursor.fetchone()
                print(check_res)
                check_reason = self.check_reason.text()
                print(check_reason)
                if check_result != '' and check_result != 'both':
                    if not check_res:
                        print("this data is new in check_modify")
                        sql = "INSERT IGNORE INTO check_modify (video_name, uid, check_result, check_reason,check_name," \
                              "modify_1_result, modify_1_flag, modify_1_name,modify_2_result, modify_2_flag, modify_2_name) VALUES (%s, %s, %s, %s, %s, %s, %s,%s,%s,%s,%s)"
                        values = (
                            video_name, uid, check_result, check_reason, check_name, modify_1_result, modify_1_flag,
                            label_1_name, modify_2_result, modify_2_flag, label_2_name)
                        print(values)
                        cursor.execute(sql, values)
                        cnx.commit()
                        print(123)
                    else:
                        sql = "UPDATE check_modify SET check_result=%s, check_reason=%s, check_name=%s,modify_1_flag=%s, modify_1_name=%s, modify_2_flag=%s, modify_2_name=%s where video_name=%s and uid=%s"
                        values = (check_result, check_reason, check_name, modify_1_flag, label_1_name, modify_2_flag,
                                  label_2_name, video_name, uid)
                        print(values)
                        cursor.execute(sql, values)
                        cnx.commit()
                elif check_result == 'both':
                    if check_res:
                        sql = "DELETE FROM check_modify where video_name=%s and uid=%s"
                        values = (video_name, uid)
                        print(values)
                        cursor.execute(sql, values)
                        cnx.commit()
                # 查询审核总数
                query = "SELECT COUNT(*) FROM label_result WHERE check_name=%s and " \
                        "check_time BETWEEN %s AND %s"
                values = (self.username, self.work_start_time, self.work_end_time)
                cursor.execute(query, values)

                # 获取查询结果
                result = cursor.fetchone()
                count = result[0]
                print("per count:", count)

                sql = "UPDATE per_job SET per_work_time = %s ,work_end_time = %s ,per_work_amount= %s WHERE name=%s and date=%s and work_type=%s and work_start_time=%s;"
                values = (
                    str(self.time_delta), self.work_end_time, count, self.username, date.today(), self.method,
                    self.work_start_time)
                cursor.execute(sql, values)
                cnx.commit()

                # 更新user表
                sql = "UPDATE user SET been_checked_amount=been_checked_amount+1 where name=%s"
                values = label_1_name
                cursor.execute(sql, values)
                cnx.commit()

                sql = "UPDATE user SET been_checked_amount=been_checked_amount+1 where name=%s"
                values = label_2_name
                cursor.execute(sql, values)
                cnx.commit()
                '''
                if self.txt_table.item(self.table_row, 7).text()=='both':
                    sql="UPDATE user SET correct_amount=correct_amount+1 where name=%s"
                    values = label_1_name
                    cursor.execute(sql, values)
                    cnx.commit()

                    sql = "UPDATE user SET correct_amount=correct_amount+1 where name=%s"
                    values = label_2_name
                    cursor.execute(sql, values)
                    cnx.commit()
                elif self.txt_table.item(self.table_row, 7).text()=='label_1':
                    sql = "UPDATE user SET correct_amount=correct_amount+1 where name=%s"
                    values = label_1_name
                    cursor.execute(sql, values)
                    cnx.commit()
                elif self.txt_table.item(self.table_row, 7).text()=='label_2':
                    sql = "UPDATE user SET correct_amount=correct_amount+1 where name=%s"
                    values = label_2_name
                    cursor.execute(sql, values)
                    cnx.commit()
                '''

            # 更新日工时
            sql = "SELECT SUM(TIME_TO_SEC(per_work_time)) AS total_work_time FROM per_job where name=%s and date=%s;"
            values = (self.username, date.today())
            cursor.execute(sql, values)
            result = cursor.fetchone()
            total_work_time = result[0]
            hour = total_work_time // 3600
            minute = (total_work_time // 60) % 60
            second = total_work_time % 60
            day_work_time_str = str(hour) + ":" + str(minute) + ":" + str(second)

            print(date.today(), "total_work_time:", day_work_time_str)

            sql = "UPDATE attendance SET daily_work_time=%s where name=%s and date=%s"
            values = (day_work_time_str, self.username, date.today())
            cursor.execute(sql, values)
            cnx.commit()
        # 更新标注文件
        self.updateLabel_txt()
        self.updateLabel_json()

    # 检测10分钟内有无提交操作，没有就停止计时
    def timer_timeout(self):
        # self.work_time.setText("00:00:00")
        self.ten_min_timer.stop()
        self.endWorkTime()

        QMessageBox.warning(None, "提示", "由于您十分钟内没有操作，系统已停止工作计时。")

    def test(self):
        print("test success!")

    # 导出标注
    def outputJson(self):
        if not self.flag:
            return
        video_dict = {}
        tv_dict = {}
        # 指定目标目录
        if self.method == "标注模式":
            # target_dir = "results/json/" + self.folder_dirname
            target_dir = "results/json/"
        if self.method == "审核模式":
            # target_dir = "checks/json/" + self.folder_dirname
            target_dir = "checks/json/"

        # 存储所有子目录名称的列表
        sub_dirs = []

        # 遍历目标目录下的所有文件和目录
        for name in os.listdir(target_dir):
            # 获取文件/目录的完整路径
            full_path = os.path.join(target_dir, name)
            # 如果是目录，则将目录名添加到子目录列表中
            if os.path.isdir(full_path):
                sub_dirs.append(full_path)

        print("sub_dirs:", sub_dirs)
        # 遍历目录
        for dir_path in sub_dirs:
            tv_name = os.path.basename(dir_path)
            tv_dict[tv_name] = {}
            if self.method == "标注模式":
                # fp = open("results/labels_" + self.folder_dirname + ".json", "w", encoding="utf-8")
                fp = open("results/labels_" + self.json.split("/")[1], "w", encoding="utf-8")
            if self.method == "审核模式":
                # fp = open("checks/labels_" + self.folder_dirname + ".json", "w", encoding="utf-8")
                fp = open("checks/checks_" + self.json.split("/")[1], "w", encoding="utf-8")
            fp.write("")
            for root, dirs, files in os.walk(dir_path):
                for file in files:
                    file_path = os.path.abspath(os.path.join(root, file))
                    print(file_path)
                    f = open(file_path, "r", encoding="utf-8")
                    data = json.load(f)
                    print(data)
                    video_name = os.path.basename(file_path).replace(".json", "")

                    tv_dict[tv_name][video_name] = data
                    tv_dict_json = json.dumps(tv_dict, ensure_ascii=False)

            fp.write(tv_dict_json)
            print("tv_dict:", tv_dict)

        QMessageBox.warning(None, "提示", "导出成功！")

    # 更新标注文件(txt)
    def updateLabel_txt(self):
        if self.method == "标注模式":
            fp = open(self.path_txt, "w", encoding="utf-8")
            for row in range(self.txt_table.rowCount()):
                for col in range(9):
                    fp.write(self.txt_table.item(row, col).text() + "//")
                fp.write("\n")
        if self.method == "审核模式":
            fp = open(self.path_txt, "w", encoding="utf-8")
            for row in range(self.txt_table.rowCount()):
                for col in range(9):
                    fp.write(self.txt_table.item(row, col).text() + "//")
                fp.write("\n")

    # 更新标注文件(json)
    def updateLabel_json(self):
        f = open(self.path_json, "r", encoding="utf-8")
        data = json.load(f)
        self.result = data
        self.result["relation"] = []
        if self.method == "标注模式":
            for row in range(self.txt_table.rowCount()):
                if self.txt_table.item(row, 5).text() != "-" and self.txt_table.item(row, 6).text() != "-":
                    item = {
                        'x': row + 1,
                        'y': int(self.txt_table.item(row, 5).text().replace("U", "")),
                        'type': self.txt_table.item(row, 6).text()
                    }
                    self.result["relation"].append(item)
        elif self.method == "审核模式":
            for row in range(self.txt_table.rowCount()):
                if row == 0:
                    continue
                if self.txt_table.item(row, 7).text() != "-" and self.txt_table.item(row, 8).text() != "-":
                    if self.txt_table.item(row, 7).text() == "both" or self.txt_table.item(row, 7).text() == "label_1":
                        label = self.txt_table.item(row, 5).text()
                        print("label ", label)
                    elif self.txt_table.item(row, 7).text() == "label_2":
                        label = self.txt_table.item(row, 6).text()
                    else:
                        label = self.txt_table.item(row, 7).text()
                    start_index = label.index("(") + 1  # 获取左括号后的索引位置
                    end_index = label.index(")")  # 获取右括号的索引位置
                    extracted_data_type = label[start_index:end_index].split(",")
                    print("extracted_data_type ", extracted_data_type)
                    x = row + 1
                    y = int(extracted_data_type[0].replace("U", ""))
                    type = extracted_data_type[1]
                    item = {
                        'x': x,
                        'y': y,
                        'type': type
                    }
                    self.result["relation"].append(item)
        result = json.dumps(self.result, ensure_ascii=False)
        fp = open(self.path_json, "w", encoding="utf-8")
        fp.write(result)

    # 初始化标注文件(json)
    def initLabel_json(self):
        self.result["relation"] = []
        result = json.dumps(self.result, ensure_ascii=False)
        fp = open(self.path_json, "w", encoding="utf-8")
        fp.write(result)

    # 上一个句子
    def lastLabel(self):
        if not self.flag:
            return
        if self.table_row != 0:
            self.txt_table.setCurrentCell(self.table_row - 1, self.table_col)  # 鼠标移动到上一行的uid单元格
        else:
            self.txt_table.setCurrentCell(self.txt_table.rowCount() - 1, self.table_col)
        self.cellClick()

    # 下一个句子
    def nextLabel(self):
        if not self.flag:
            return
        if self.table_row != self.txt_table.rowCount() - 1:
            self.txt_table.setCurrentCell(self.table_row + 1, self.table_col)  # 鼠标移动到下一行的uid单元格
        else:
            self.txt_table.setCurrentCell(0, self.table_col)
        self.cellClick()

    # 跳转句子
    def jumpLabel(self):
        if not self.flag:
            return
        if self.jump_number.value() <= self.txt_table.rowCount():
            self.txt_table.setCurrentCell(self.jump_number.value() - 1, 0)
            self.cellClick()
        else:
            print("跳转失败！jump_number大于总句子个数！")

    # 上一个视频
    def lastVideo(self):
        # 将关系列表清空
        self.rList = []
        if self.task_list.currentRow() != 0:
            self.task_list.setCurrentRow(self.task_list.currentRow() - 1)
        else:
            self.task_list.setCurrentRow(self.task_list.count() - 1)

    # 下一个视频
    def nextVideo(self):
        # 将关系列表清空
        self.rList = []
        if self.task_list.currentRow() != self.task_list.count() - 1:
            self.task_list.setCurrentRow(self.task_list.currentRow() + 1)
        else:
            self.task_list.setCurrentRow(0)


# 用户界面
class UserWin(QMainWindow, userwinui):
    # close_signal = pyqtSignal(str)

    def __init__(self):
        QMainWindow.__init__(self)
        userwinui.__init__(self)
        self.setupUi(self)

        self.login_username = ""
        self.login_password = ""
        self.login_method = ""

        self.init()
        self.btnBind()

    def init(self):
        self.setWindowIcon(QIcon("icon/pen.png"))
        self.user_picture.setPixmap(QPixmap("icon/user.PNG"))
        self.user_picture.setScaledContents(True)
        self.auto_assign.setVisible(False)

    def btnBind(self):
        self.pushButton.clicked.connect(self.log_out)
        self.auto_assign.clicked.connect(self.autoAssign)

    def log_out(self):
        self.close()
        self.logWin = LoginWin()
        self.logWin.show()
        self.logWin.username.setText(self.login_username)
        self.logWin.password.setText(self.login_password)

    # 槽函数，接收用户信息
    def user_slot(self, username, password, method, hour, minute, second, count):
        self.username.setText(username)

        print("user:", username, method)
        self.login_username = username
        self.login_password = password

        # 执行日label_count查询语句
        query = "SELECT COUNT(*) FROM label_result WHERE (label_1_name=%s and label_1_time BETWEEN %s AND %s) " \
                "or (label_2_name=%s and label_2_time BETWEEN %s AND %s)"
        values = (
            username, datetime.now().strftime("%Y-%m-%d") + " 00:00:00",
            datetime.now().strftime("%Y-%m-%d") + " 23:59:59",
            username, datetime.now().strftime("%Y-%m-%d") + " 00:00:00",
            datetime.now().strftime("%Y-%m-%d") + " 23:59:59",)
        cursor.execute(query, values)

        result = cursor.fetchone()
        today_label_count = result[0]
        print("today_label_count：", today_label_count)

        # 执行日check_count查询语句
        query = "SELECT COUNT(*) FROM label_result WHERE check_name=%s and check_time BETWEEN %s AND %s"
        values = (
            username, datetime.now().strftime("%Y-%m-%d") + " 00:00:00",
            datetime.now().strftime("%Y-%m-%d") + " 23:59:59")
        cursor.execute(query, values)

        result = cursor.fetchone()
        today_check_count = result[0]
        if not today_check_count:
            today_check_count = 0
        print("today_check_count：", today_check_count)

        # 执行任务情况更新语句
        sql = "UPDATE task_completion SET check_complete = %s,label_complete=%s where name=%s and date=%s;"
        values = (today_check_count, today_label_count, username, date.today())
        cursor.execute(sql, values)
        cnx.commit()

        sql = "UPDATE task_completion SET if_reach_goal = 'yes' WHERE label_complete >=label_goal and check_complete >= check_goal;"
        cursor.execute(sql)
        cnx.commit()

        query = "SELECT * FROM task_completion where date=%s and name=%s"
        values = (date.today(), '李星宇')
        cursor.execute(query, values)
        res = cursor.fetchall()

        self.label_complete.setText(str(today_label_count) + "个")
        self.check_complete.setText(str(today_check_count) + "个")

        if res:
            print(res)
            label_goal = res[0][2]
            check_goal = res[0][4]
            if_reach_goal = res[0][6]
            self.label_goal.setText(str(label_goal) + "个")
            self.check_goal.setText(str(check_goal) + "个")

            if if_reach_goal == 'yes':
                self.if_reach_goal.setText("任务已达标")
            else:
                self.if_reach_goal.setText("任务未达标")
        else:
            print("can not find the name or the date")

        # 查询周任务
        sql = "SELECT surplus_task,task_count FROM surplus_task where name=%s "
        values = username
        cursor.execute(sql, values)
        res = cursor.fetchone()
        print(res)
        if res:
            if res[1] != 0:  # 剩余任务不是0
                self.auto_assign.setVisible(False)
                task = res[0].split("|")
                for task_i in task:
                    if task_i:
                        self.task.addItem(task_i)
            else:
                self.task.addItem('本期任务已完成')
                self.task.addItem('是否获取新任务？')
                self.auto_assign.setVisible(True)

        '''
        sql = "SELECT task,week,count FROM task_week where name=%s "
        values = username
        cursor.execute(sql, values)
        res = cursor.fetchall()
        for i in range(len(res)):
            time = res[i][1]
            start_date = time.split("-")[0]
            end_date = time.split("-")[1]
            print(start_date, end_date)
            start_date2 = start_date.split("/")
            end_date2 = end_date.split("/")
            # 指定起始日期和结束日期
            start_date = date(int(start_date2[0]), int(start_date2[1]), int(start_date2[2]))
            end_date = date(int(end_date2[0]), int(end_date2[1]), int(end_date2[2]))
            # 要判断的日期
            check_date = date.today()
            # 判断日期是否在指定范围内
            if start_date <= check_date <= end_date:
                print(check_date, "is between the specified dates.")
                print(username, "本周任务", res[i][0])
                str_count = str(res[i][2]) + "个语句"
                a = res[i][0].split(",")
                # self.task.addItem(str(start_date)+"~"+str(end_date))
                for i in range(len(a)):
                    if a[i] != "":
                        self.task.addItem(a[i])
                self.label_week_goal.setText(str_count)
            else:
                print(check_date, "is not between the specified dates.")
        '''

        # 执行总label_count查询语句
        query = "SELECT COUNT(*) FROM label_result WHERE (label_1_name=%s and label_1_time is not null ) or (label_2_name=%s and label_2_time is not null)"
        values = (username, username)
        cursor.execute(query, values)
        result = cursor.fetchone()
        label_count = result[0]
        print("label_count：", label_count)

        self.label_num.setText(str(label_count) + "个")

        # 执行总check_count查询语句
        query = "SELECT COUNT(*) FROM label_result WHERE check_name=%s and check_time is not null"
        values = username
        cursor.execute(query, values)
        result = cursor.fetchone()
        check_count = result[0]
        print("check_count：", check_count)

        self.check_num.setText(str(check_count) + "个")

        # 总工时计算
        sql = "SELECT SUM(TIME_TO_SEC(daily_work_time)) AS work_time FROM attendance where name=%s"
        values = username
        cursor.execute(sql, values)
        res = cursor.fetchone()
        print("work_time", res[0])
        total_work_time = res[0]
        hour = total_work_time // 3600
        minute = (total_work_time // 60) % 60
        second = total_work_time % 60
        work_time_str = str(hour) + ":" + str(minute) + ":" + str(second)
        self.total_work_time.setText(str(hour) + "时" + str(minute) + "分" + str(second) + "秒")

        sql = "UPDATE user SET label_amount=%s, check_amount=%s,work_time=%s where name=%s"
        values = (label_count, check_count, work_time_str, username)
        cursor.execute(sql, values)
        cnx.commit()

        # 今日工时
        sql = "SELECT daily_work_time FROM attendance where name=%s and date=%s"
        values = (username, date.today())
        cursor.execute(sql, values)
        res = cursor.fetchone()
        hour, minute, second = str(res[0]).split(":")
        today_work_time_str = str(hour) + "时" + str(minute) + "分" + str(second) + "秒"
        print(today_work_time_str)
        self.today_work_time.setText(today_work_time_str)

        # 标注正确个数，被审核个数
        sql = "SELECT label_1_name,label_2_name,check_result FROM label_result where label_1_name=%s or label_2_name=%s"
        values = (username, username)
        cursor.execute(sql, values)
        res = cursor.fetchall()
        print(res)
        label_correct = 0
        for i in range(len(res)):
            if res[0][0] == username:
                if res[i][2] == "label_1" or res[i][2] == "both":
                    label_correct = label_correct + 1

            elif res[0][1] == username:
                if res[i][2] == "label_2" or res[i][2] == "both":
                    label_correct = label_correct + 1

        self.label_correct_num.setText(str(label_correct) + "个")
        sql = "UPDATE user SET correct_amount=%s where name=%s"
        values = (label_correct, username)
        cursor.execute(sql, values)
        cnx.commit()

        sql = "SELECT been_checked_amount FROM user where name=%s"
        values = username
        cursor.execute(sql, values)
        res = cursor.fetchone()
        self.been_checked_num.setText(str(res[0]) + "个")

    # 获取新任务
    def autoAssign(self):
        self.task.clear()
        print("剩余任务为空，则自动从待分配的任务中进行分配")
        not_assign_task = []
        assign_task_1 = []
        sql1 = "SELECT inst_id,assign_flag FROM video_assign_copy where assign_flag='待分配'"
        sql2 = "SELECT inst_id,assign_flag FROM video_assign_copy where assign_flag='已分配1'"
        cursor.execute(sql1)
        res1 = cursor.fetchall()
        cursor.execute(sql2)
        res2 = cursor.fetchall()
        if res1:  # 待分配
            for i in res1:
                not_assign_task.append(i[0])
            print(len(not_assign_task))
            if len(not_assign_task) >= 2:  # 单次分配=2,小于剩余任务总数
                surplus_task_A = ""
                for i in range(2):
                    # 更新任务分配表
                    sql = "UPDATE video_assign_copy SET assign_name1=%s,assign_flag='已分配1' where inst_id=%s"
                    values = (self.login_username, not_assign_task[i])
                    cursor.execute(sql, values)
                    cnx.commit()
                    surplus_task_A = surplus_task_A + not_assign_task[i] + "|"
                    self.task.addItem(not_assign_task[i])
                # 更新剩余任务表
                sqlA = "UPDATE surplus_task SET surplus_task=%s ,task_count=%s where name=%s"
                valuesA = (surplus_task_A, 2, self.login_username)
                cursor.execute(sqlA, valuesA)
                cnx.commit()

            else:  # 单次分配>剩余任务总数
                for i in range(not_assign_task):
                    # 更新任务分配表
                    sql = "UPDATE video_assign_copy SET assign_name1=%s,assign_flag='已分配1' where inst_id=%s"
                    values = (self.login_username, not_assign_task[i])
                    cursor.execute(sql, values)
                    cnx.commit()
                    surplus_task_A = surplus_task_A + not_assign_task[i] + "|"
                    self.task.addItem(not_assign_task[i])
                # 更新剩余任务表self.login_username
                sqlA = "UPDATE surplus_task SET surplus_task=%s ,task_count=%s where name=%s"
                valuesA = (surplus_task_A, 2, self.login_username)
                cursor.execute(sqlA, valuesA)
                cnx.commit()

        elif res2:  # 已分配1
            for i in res2:
                assign_task_1.append(i[0])
            print(len(assign_task_1))
            if len(assign_task_1) >= 2:  # 单次分配=2,小于剩余任务总数
                surplus_task_A = ""
                for i in range(2):
                    # 更新任务分配表
                    sql = "UPDATE video_assign_copy SET assign_name2=%s,assign_flag='已分配2' where inst_id=%s"
                    values = (self.login_username, assign_task_1[i])
                    cursor.execute(sql, values)
                    cnx.commit()
                    surplus_task_A = surplus_task_A + assign_task_1[i] + "|"
                    self.task.addItem(assign_task_1[i])
                # 更新剩余任务表
                sqlA = "UPDATE surplus_task SET surplus_task=%s ,task_count=%s where name=%s"
                valuesA = (surplus_task_A, 2, self.login_username)
                cursor.execute(sqlA, valuesA)
                cnx.commit()

            else:  # 单次分配>剩余任务总数
                for i in range(assign_task_1):
                    # 更新任务分配表
                    sql = "UPDATE video_assign_copy SET assign_name2=%s,assign_flag='已分配2' where inst_id=%s"
                    values = (self.login_username, assign_task_1[i])
                    cursor.execute(sql, values)
                    cnx.commit()
                    surplus_task_A = surplus_task_A + assign_task_1[i] + "|"
                    self.task.addItem(assign_task_1[i])
                # 更新剩余任务表
                sqlA = "UPDATE surplus_task SET surplus_task=%s ,task_count=%s where name=%s"
                valuesA = (surplus_task_A, 2, self.login_username)
                cursor.execute(sqlA, valuesA)
                cnx.commit()


# 管理界面
class AdminWin(QMainWindow, adminwinui):
    combo_signal = ComboBoxSignal()

    def __init__(self):
        QMainWindow.__init__(self)
        userwinui.__init__(self)
        self.sort_flag = 0
        self.setupUi(self)

        self.login_username = ""
        self.login_password = ""
        self.login_method = ""

        self.sentence_count = 0
        self.task = ""
        self.init()
        self.btnBind()
        self.signals()

    # 信号槽绑定
    def signals(self):
        self.week.currentTextChanged.connect(self.on_value_changed)
        self.name.currentTextChanged.connect(self.on_value_changed)
        self.combo_signal.value_changed.connect(self.on_value_change_detected)

    def on_value_changed(self, value):
        self.combo_signal.value_changed.emit(value)

    def on_value_change_detected(self, value):
        print("update:", value)
        self.task_table.setRowCount(0)
        sql = "SELECT * FROM video_assign where assign_week=%s and (assign_name1=%s or assign_name2=%s)"
        values = (self.week.currentText(), self.name.currentText(), self.name.currentText())
        cursor.execute(sql, values)
        res = cursor.fetchall()
        self.task_table.setRowCount(0)
        self.sentence_count = 0
        for i in range(len(res)):
            print(res[i])
            row_new = self.task_table.rowCount()  # 返回当前行数(尾部)
            print(row_new)
            self.task_table.insertRow(row_new)
            self.task_table.setItem(row_new, 0, QTableWidgetItem(res[i][0]))  # 分配视频名
            self.task_table.setItem(row_new, 1, QTableWidgetItem(str(res[i][1]) + "个语句"))  # 语句个数
            self.task_table.setItem(row_new, 2, QTableWidgetItem(res[i][2]))  # 任务时间
            if self.name.currentText() == res[i][3]:
                self.task_table.setItem(row_new, 3, QTableWidgetItem(res[i][3]))  # 分配人姓名
            if self.name.currentText() == res[i][4]:
                self.task_table.setItem(row_new, 3, QTableWidgetItem(res[i][4]))  # 分配人姓名
            self.sentence_count += res[i][1]
        self.video_count.setText(str(self.task_table.rowCount()) + "个视频")
        self.utt_count.setText(str(self.sentence_count) + "个语句")

        print("任务更新成功")

    def init(self):
        self.setWindowIcon(QIcon("icon/pen.png"))
        sql = "SELECT * FROM video_assign where assign_week=%s and (assign_name1=%s or assign_name2=%s)"
        values = (self.week.currentText(), self.name.currentText(), self.name.currentText())
        cursor.execute(sql, values)
        res = cursor.fetchall()
        self.task_table.setRowCount(0)
        self.sentence_count = 0
        for i in range(len(res)):
            print(res[i])
            row_new = self.task_table.rowCount()  # 返回当前行数(尾部)
            print(row_new)
            self.task_table.insertRow(row_new)
            self.task_table.setItem(row_new, 0, QTableWidgetItem(res[i][0]))
            self.task_table.setItem(row_new, 1, QTableWidgetItem(str(res[i][1]) + "个语句"))
            self.task_table.setItem(row_new, 2, QTableWidgetItem(res[i][2]))
            self.task_table.setItem(row_new, 3, QTableWidgetItem(res[i][3]))
            self.sentence_count += res[i][1]
        self.video_count.setText(str(self.task_table.rowCount()) + "个视频")
        self.utt_count.setText(str(self.sentence_count) + "个语句")

        self.video_table.resizeColumnsToContents()

        self.refreshUser()
        self.refreshChecker()

    def btnBind(self):
        # self.choose_folder.clicked.connect(self.choose_tv)  # 选择视频文件夹
        self.submit.clicked.connect(self.submit_task)  # 提交
        self.clear.clicked.connect(self.clear_task)  # 清空任务
        # self.tv_list.itemClicked.connect(self.onClickedTvList)  # 点击电视列表
        # self.video_list.itemClicked.connect(self.onClickedVideoList)  # 点击视频列表
        self.video_table.cellClicked.connect(self.onClickedVideoTable)  # 点击视频表格
        # self.task_list.itemClicked.connect(self.onClickedTaskList)  # 点击任务列表
        self.task_table.doubleClicked.connect(self.delete_row)  # 双击删除表格行
        # self.import_json.clicked.connect(self.importJson)   # 导入json
        self.import_all.clicked.connect(self.importAll)  # 导入全部视频
        self.sort_video.clicked.connect(self.sortVideo)  # 排序
        self.refresh.clicked.connect(self.refreshTask)  # 更新任务
        self.refresh_user.clicked.connect(self.refreshUser)  # 更新标注情况表
        self.refresh_checker.clicked.connect(self.refreshChecker)  # 更新审核情况表

    def refreshChecker(self):
        # 查询审核数据个数
        data = {'石心': 0, '赵诉显': 0, '徐丽莹': 0, '李星宇': 0}
        for name in data:
            sql = "SELECT check_name, COUNT(*) FROM label_result WHERE check_name=%s"
            cursor.execute(sql, (name,))
            res = cursor.fetchone()
            if res:
                data[name] = res[1]
                row_new = self.checker_table.rowCount()  # 返回当前行数(尾部)
                print("row:", row_new)
                self.checker_table.insertRow(row_new)
                self.checker_table.setItem(row_new, 0, QTableWidgetItem(name))
                self.checker_table.setItem(row_new, 1, QTableWidgetItem(str(data[name])))
                self.checker_table.resizeColumnsToContents()

        print(data)

    def refreshUser(self):
        # 正确个数
        data_correct = {'李星宇': 0, '万志斌': 0, '徐丽莹': 0, '漆力瑞': 0, '李兆煜': 0}
        sql = "SELECT label_1_name,label_2_name,check_result FROM label_result where check_result !=''"
        cursor.execute(sql)
        res = cursor.fetchall()
        print(res)
        for i in range(len(res)):
            if res[i][2] == 'both':
                print("都正确")
                data_correct[res[i][0]] += 1
                data_correct[res[i][1]] += 1
            elif res[i][2] == 'label_1':
                print(res[0][0], "正确")
                data_correct[res[i][0]] += 1
            elif res[i][2] == 'label_2':
                print(res[0][1], "正确")
                data_correct[res[i][1]] += 1
            else:
                print("都不正确", res[i][2])
        print(data_correct)
        for index, key in enumerate(data_correct.keys()):
            print(key, data_correct[key])
            sql = "UPDATE user SET correct_amount=%s where name=%s"
            values = (data_correct[key], key)
            cursor.execute(sql, values)
            cnx.commit()
        # 审核总数
        data = {'李星宇': 0, '万志斌': 0, '徐丽莹': 0, '漆力瑞': 0, '李兆煜': 0}
        sql = "SELECT label_1_name,label_2_name,check_result FROM label_result where check_result !='' and label_1_result!='' and label_2_result!=''"
        cursor.execute(sql)
        res = cursor.fetchall()
        # print(res)
        for i in range(len(res)):
            data[res[i][0]] += 1
            data[res[i][1]] += 1
        print(data)

        for index, key in enumerate(data.keys()):
            print(key, data[key])
            sql = "UPDATE user SET been_checked_amount=%s where name=%s"
            values = (data[key], key)
            cursor.execute(sql, values)
            cnx.commit()

        sql = "SELECT name,label_amount,been_checked_amount,correct_amount FROM user where name=%s or name=%s or name=%s or name=%s or name=%s"
        values = ('李星宇', '万志斌', '徐丽莹', '漆力瑞', '李兆煜')
        cursor.execute(sql, values)
        res = cursor.fetchall()
        for i in range(5):
            row_new = self.user_table.rowCount()  # 返回当前行数(尾部)
            print("row:", row_new)
            self.user_table.insertRow(row_new)
            self.user_table.setItem(row_new, 0, QTableWidgetItem(res[i][0]))
            self.user_table.setItem(row_new, 1, QTableWidgetItem(str(res[i][1])))
            self.user_table.setItem(row_new, 2, QTableWidgetItem(str(res[i][2])))
            self.user_table.setItem(row_new, 3, QTableWidgetItem(str(res[i][3])))
            self.user_table.setItem(row_new, 4, QTableWidgetItem(str(round(res[i][3] / res[i][2], 4))))
            self.user_table.resizeColumnsToContents()

        print("刷新成功")

    def refreshTask(self):
        sql = "SELECT * FROM video_assign where assign_week=%s and (assign_name1=%s or assign_name2=%s)"
        values = (self.week.currentText(), self.name.currentText(), self.name.currentText())
        cursor.execute(sql, values)
        res = cursor.fetchall()
        self.task_table.setRowCount(0)
        self.sentence_count = 0
        for i in range(len(res)):
            print(res[i])
            row_new = self.task_table.rowCount()  # 返回当前行数(尾部)
            print(row_new)
            self.task_table.insertRow(row_new)
            self.task_table.setItem(row_new, 0, QTableWidgetItem(res[i][0]))
            self.task_table.setItem(row_new, 1, QTableWidgetItem(str(res[i][1]) + "个语句"))
            self.task_table.setItem(row_new, 2, QTableWidgetItem(res[i][2]))
            if res[i][3] == self.name.currentText():
                self.task_table.setItem(row_new, 3, QTableWidgetItem(res[i][3]))
            if res[i][4] == self.name.currentText():
                self.task_table.setItem(row_new, 3, QTableWidgetItem(res[i][4]))
            self.sentence_count += res[i][1]
        self.video_count.setText(str(self.task_table.rowCount()) + "个视频")
        self.utt_count.setText(str(self.sentence_count) + "个语句")

        for i in range(self.video_table.rowCount()):
            sql = "SELECT * FROM video_assign where inst_id=%s"
            values = self.video_table.item(i, 0).text()
            cursor.execute(sql, values)
            res = cursor.fetchone()
            self.video_table.item(i, 2).setText(res[5])

        print("刷新成功")

    def delete_row(self, i):
        '''
        for video_i in range(self.video_table.rowCount()):
            if self.task_table.item(i.row(), 0).text()==self.video_table.item(video_i.row(), 0).text():
                print(123)
        '''
        self.sentence_count -= int(self.task_table.item(i.row(), 1).text().replace("个语句", ""))

        self.task_table.removeRow(i.row())
        self.utt_count.setText(str(self.sentence_count) + "个语句")
        self.video_count.setText(str(self.task_table.rowCount()) + "个视频")

    def sortVideo(self):

        item_text_all = [self.video_table.item(index, 0).text() + "  " + self.video_table.item(index, 1).text() for
                         index in range(self.video_table.rowCount())]
        print(item_text_all)
        a = []
        for item_text in item_text_all:
            a_item = (item_text.split("  ")[0], item_text.split("  ")[1])
            a.append(a_item)
        print(a)
        sorted_list = sorted(a, key=lambda x: int(x[1].replace("个语句", "")))
        print(sorted_list)

        index = 0
        length = len(sorted_list)
        print(length)
        for i in range(length):
            self.video_table.item(i, 0).setText(sorted_list[i][0])
            self.video_table.item(i, 1).setText(sorted_list[i][1])

    # 导入全部
    def importAll(self):

        sql = "SELECT * FROM video_assign"
        cursor.execute(sql)
        res = cursor.fetchall()
        self.video_table.setRowCount(0)
        for i in range(len(res)):
            print(res[i])
            row_new = self.video_table.rowCount()  # 返回当前行数(尾部)
            self.video_table.insertRow(row_new)
            self.video_table.setItem(row_new, 0, QTableWidgetItem(res[i][0]))
            self.video_table.setItem(row_new, 1, QTableWidgetItem(str(res[i][1]) + "个语句"))
            self.video_table.setItem(row_new, 2, QTableWidgetItem(res[i][5]))
            self.video_table.setItem(row_new, 3, QTableWidgetItem(res[i][3] + "," + res[i][4]))

    def submit_task(self):
        self.task = ""

        for i in range(self.task_table.rowCount()):
            print(self.task_table.item(i, 0).text())
            item = self.task_table.item(i, 2)
            item.setText(self.week.currentText())
            item = self.task_table.item(i, 3)
            item.setText(self.name.currentText())

            item1 = self.task_table.item(i, 0)
            self.task += item1.text() + ","

            sql = "SELECT assign_name1,assign_name2 FROM video_assign WHERE inst_id=%s"
            values = self.task_table.item(i, 0).text()
            cursor.execute(sql, values)
            res = cursor.fetchone()
            print(res[0], res[1])
            if not res[0] or res[0] == self.name.currentText():
                sql = "UPDATE video_assign SET assign_week=%s, assign_name1=%s,assign_flag=%s WHERE inst_id=%s"
                values = (
                    self.week.currentText(), self.name.currentText(), "已分配1", self.task_table.item(i, 0).text())
                cursor.execute(sql, values)
                cnx.commit()
            if res[0] and res[0] != self.name.currentText():
                sql = "UPDATE video_assign SET assign_week=%s, assign_name2=%s,assign_flag=%s WHERE inst_id=%s"
                values = (
                    self.week.currentText(), self.name.currentText(), "已分配2", self.task_table.item(i, 0).text())
                cursor.execute(sql, values)
                cnx.commit()

        query = "INSERT IGNORE INTO task_week (name, week) VALUES (%s, %s)"
        values = (self.name.currentText(), self.week.currentText())
        cursor.execute(query, values)
        cnx.commit()

        sql = "UPDATE task_week SET task=%s, count=%s WHERE name=%s and week=%s"
        values = (
            self.task, int(self.utt_count.text().replace("个语句", "")), self.name.currentText(),
            self.week.currentText())
        cursor.execute(sql, values)
        cnx.commit()
        # self.refreshTask()
        QMessageBox.warning(None, "提示", "提交成功！")

    def clear_task(self):

        self.sentence_count = 0
        self.task = ""
        sql = "UPDATE task_week SET task=%s, count=%s WHERE name=%s and week=%s"
        values = ("", 0, self.name.currentText(), self.week.currentText())
        cursor.execute(sql, values)
        cnx.commit()
        for i in range(self.task_table.rowCount()):
            id = self.task_table.item(i, 0).text()
            sql = "SELECT assign_name1,assign_name2,assign_flag,assign_week FROM video_assign where inst_id=%s"
            values = id
            cursor.execute(sql, values)
            res = cursor.fetchone()
            if res[2] == "已分配1":
                assign_flag = "未分配"
                assign_week = ""
            if res[2] == "已分配2":
                assign_flag = "已分配1"
                assign_week = res[3]
            if self.name.currentText() == res[0]:
                sql = "UPDATE video_assign SET assign_week=%s, assign_name1=%s,assign_flag=%s WHERE inst_id=%s"
                values = (assign_week, "", assign_flag, id)
                cursor.execute(sql, values)
                cnx.commit()
            if self.name.currentText() == res[1]:
                sql = "UPDATE video_assign SET assign_week=%s, assign_name2=%s,assign_flag=%s WHERE inst_id=%s"
                values = (assign_week, "", assign_flag, id)
                cursor.execute(sql, values)
                cnx.commit()
        self.task_table.setRowCount(0)
        QMessageBox.warning(None, "提示", "清空成功！")

    '''
    def onClickedTvList(self,item):
        print("Item clicked:", item.text())
        #print(item.text().split("  /")[1])
        f = open("data/"+item.text().split("  /")[1]+".json", "r", encoding="utf-8")
        data = json.load(f)
        tv_key=item.text().split("  /")[0]
        for video_key in data[tv_key].keys():
            print(video_key)
            dialog = data[tv_key][video_key]["Dialog"]
            i = 0
            for dialog_key in dialog.keys():
                i = i + 1
            total_utt = i
            new_item_text = video_key+"  "+str(total_utt)+"个语句"
            if new_item_text not in [self.video_list.item(index).text() for index in range(self.video_list.count())]:
                # 如果不存在，则添加新行
                self.video_list.addItem(new_item_text)
    '''

    def onClickedVideoTable(self):
        for i in self.video_table.selectedItems():
            print(i.row() + 1, i.column() + 1, i.text())
            assign_flag = self.video_table.item(i.row(), 2).text()
            inst_id = self.video_table.item(i.row(), 0).text()

            sql = "SELECT assign_name1,assign_name2 FROM video_assign where inst_id=%s"
            values = inst_id
            cursor.execute(sql, values)
            res = cursor.fetchone()
            if res[0] == self.name.currentText() or res[1] == self.name.currentText():
                QMessageBox.warning(None, "提示", "重复分配！")
                return
            '''
            if assign_flag=="未分配":
                self.video_table.item(i.row(), 2).setText("已分配1")
            if assign_flag=="已分配1":
                self.video_table.item(i.row(), 2).setText("已分配2")
            '''
            sentence_count = self.video_table.item(i.row(), 1).text()

            self.sentence_count += int(sentence_count.replace("个语句", ""))
            self.utt_count.setText(str(self.sentence_count) + "个语句")
            row_new = self.task_table.rowCount()  # 返回当前行数(尾部)
            self.task_table.insertRow(row_new)
            self.task_table.setItem(row_new, 0, QTableWidgetItem(inst_id))
            self.task_table.setItem(row_new, 1, QTableWidgetItem(sentence_count))
            self.task_table.setItem(row_new, 2, QTableWidgetItem(""))
            self.task_table.setItem(row_new, 3, QTableWidgetItem(""))
            self.video_count.setText(str(row_new + 1) + "个视频")
            self.task_table.resizeColumnsToContents()

        '''
        if item.text() not in [self.task_list.item(index).text() for index in range(self.task_list.count())]:
            # 如果不存在，则添加新行
            self.task_list.addItem(item.text())
            self.sentence_count+=int(item.text().split("  ")[1].replace("个语句",""))
            self.utt_count.setText(str(self.sentence_count)+"个语句")
            video_count=self.task_list.count()
            self.video_count.setText(str(video_count)+"个视频")
        '''

    def onClickedTaskList(self, item):
        print("Item clicked:", item.text())
        sub = int(item.text().split("  ")[1].replace("个语句", ""))
        print(sub)
        self.sentence_count -= sub
        print(self.sentence_count)
        row = self.task_list.row(item)
        self.task_list.takeItem(row)
        self.utt_count.setText(str(self.sentence_count) + "个语句")


class ModifyWin(QMainWindow, modifywinui):
    def __init__(self):
        QMainWindow.__init__(self)
        modifywinui.__init__(self)

        self.selected_row = None
        self.setupUi(self)

        self.username = ""
        self.method = ""

        self.init()
        self.btnBind()

    # 信号槽绑定
    def modify_slot(self, username, method):
        print("user:", username, method)
        self.username = username
        self.method = method
        self.refreshModify()
        if self.method == "标注模式":
            self.submit_appeal.setText("提交申诉")
            self.withdraw_appeal.setText("撤回申诉")
        if self.method == "审核模式":
            self.submit_appeal.setText("通过申诉")
            self.withdraw_appeal.setText("驳回申诉")

    def init(self):
        self.setWindowIcon(QIcon("icon/pen.png"))

    def btnBind(self):
        self.refresh.clicked.connect(self.refreshModify)
        self.submit_appeal.clicked.connect(self.submitAppeal)
        self.modify_table.cellClicked.connect(self.tableCellClicked)
        self.withdraw_appeal.clicked.connect(self.withdrawAppeal)

    def tableCellClicked(self):
        selected_cells = self.modify_table.selectedItems()
        for item in selected_cells:
            self.selected_row = item.row()
            self.selected_column = item.column()
            print("当前选中行：", self.selected_row)

    def submitAppeal(self):
        if self.method == "标注模式":
            video_name = self.modify_table.item(self.selected_row, 0).text()
            uid = self.modify_table.item(self.selected_row, 1).text()
            sql = "SELECT modify_1_name,modify_2_name FROM check_modify where video_name=%s and uid=%s"
            values = (video_name, uid)
            cursor.execute(sql, values)
            res = cursor.fetchone()
            print(res[0], res[1])
            if res[0] == self.username:
                sql = "UPDATE check_modify SET appeal_1_reason=%s where video_name=%s and uid=%s and modify_1_name=%s"
                values = (self.appeal_reason.text(), video_name, uid, self.username)
                cursor.execute(sql, values)
                cnx.commit()
            if res[1] == self.username:
                sql = "UPDATE check_modify SET appeal_2_reason=%s where video_name=%s and uid=%s and modify_2_name=%s"
                values = (self.appeal_reason.text(), video_name, uid, self.username)
                cursor.execute(sql, values)
                cnx.commit()
            print("提交申诉")
            self.modify_table.setItem(self.selected_row, 4, QTableWidgetItem(self.appeal_reason.text()))
            self.modify_table.setItem(self.selected_row, 5, QTableWidgetItem(self.username))
        if self.method == "审核模式":
            video_name = self.modify_table.item(self.selected_row, 0).text()
            uid = self.modify_table.item(self.selected_row, 1).text()
            sql = "UPDATE check_modify SET appeal_1_reply=%s where video_name=%s and uid=%s and modify_1_name=%s"
            values = ('通过', video_name, uid, self.modify_table.item(self.selected_row, 5).text())
            cursor.execute(sql, values)
            cnx.commit()
            print("通过申诉")

            self.modify_table.setItem(self.selected_row, 6, QTableWidgetItem('通过'))

    def withdrawAppeal(self):
        if self.method == "标注模式":
            video_name = self.modify_table.item(self.selected_row, 0).text()
            uid = self.modify_table.item(self.selected_row, 1).text()
            sql = "SELECT modify_1_name,modify_2_name FROM check_modify where video_name=%s and uid=%s"
            values = (video_name, uid)
            cursor.execute(sql, values)
            res = cursor.fetchone()
            print(res[0], res[1])
            if res[0] == self.username:
                sql = "UPDATE check_modify SET appeal_1_reason=%s where video_name=%s and uid=%s and modify_1_name=%s"
                values = ('', video_name, uid, self.username)
                cursor.execute(sql, values)
                cnx.commit()
            if res[1] == self.username:
                sql = "UPDATE check_modify SET appeal_2_reason=%s where video_name=%s and uid=%s and modify_2_name=%s"
                values = ('', video_name, uid, self.username)
                cursor.execute(sql, values)
                cnx.commit()
            print("撤回申诉")
            self.modify_table.setItem(self.selected_row, 4, QTableWidgetItem(''))
            self.modify_table.setItem(self.selected_row, 5, QTableWidgetItem(''))
        if self.method == "审核模式":
            print("驳回申诉")
            video_name = self.modify_table.item(self.selected_row, 0).text()
            uid = self.modify_table.item(self.selected_row, 1).text()
            sql = "UPDATE check_modify SET appeal_1_reply=%s where video_name=%s and uid=%s and modify_1_name=%s"
            values = ('驳回', video_name, uid, self.modify_table.item(self.selected_row, 5).text())
            cursor.execute(sql, values)
            cnx.commit()
            self.modify_table.setItem(self.selected_row, 6, QTableWidgetItem('驳回'))

    def refreshModify(self):
        self.modify_table.setRowCount(0)
        if self.method == "标注模式":
            sql = "SELECT video_name,uid,check_result,check_reason,modify_1_name,modify_1_flag," \
                  "modify_2_name, modify_2_flag,appeal_1_reason,appeal_1_reply,appeal_2_reason,appeal_2_reply FROM check_modify " \
                  "where modify_1_name=%s or modify_2_name=%s"
            values = (self.username, self.username)
            cursor.execute(sql, values)
            res = cursor.fetchall()
            print(res)
            need_modify_count = 0

            for i in range(len(res)):
                video_name = res[i][0]
                uid = res[i][1]
                sql = "SELECT label_1_result,label_2_result FROM label_result where video_name=%s and uid=%s"
                values = (video_name, uid)
                cursor.execute(sql, values)
                modify_res = cursor.fetchone()
                if res[i][2] == 'label_1':
                    check_result = modify_res[0]
                    print(check_result)
                elif res[i][2] == 'label_2':
                    check_result = modify_res[1]
                    print(check_result)
                else:
                    check_result = res[i][2]
                    print(check_result)
                check_reason = res[i][3]
                modify_1_name = res[i][4]
                modify_1_flag = res[i][5]
                modify_2_name = res[i][6]
                modify_2_flag = res[i][7]
                appeal_1_reason = res[i][8]
                appeal_1_reply = res[i][9]
                appeal_2_reason = res[i][10]
                appeal_2_reply = res[i][11]
                if (modify_1_name == self.username and modify_1_flag == '待修改') or (
                        modify_2_name == self.username and modify_2_flag == '待修改'):
                    need_modify_count += 1
                    row_new = self.modify_table.rowCount()  # 返回当前行数(尾部)
                    self.modify_table.resizeColumnsToContents()
                    self.modify_table.insertRow(row_new)
                    self.modify_table.setItem(row_new, 0, QTableWidgetItem(video_name))
                    self.modify_table.setItem(row_new, 1, QTableWidgetItem(str(uid)))
                    self.modify_table.setItem(row_new, 2, QTableWidgetItem("未通过，建议修改为:" + check_result))
                    self.modify_table.setItem(row_new, 3, QTableWidgetItem(check_reason))
                    if modify_1_name == self.username:
                        self.modify_table.setItem(row_new, 4, QTableWidgetItem(appeal_1_reason))
                        self.modify_table.setItem(row_new, 6, QTableWidgetItem(appeal_1_reply))
                        if appeal_1_reason != '':
                            self.modify_table.setItem(row_new, 5, QTableWidgetItem(self.username))
                    if modify_2_name == self.username:
                        self.modify_table.setItem(row_new, 4, QTableWidgetItem(appeal_2_reason))
                        self.modify_table.setItem(row_new, 6, QTableWidgetItem(appeal_2_reply))
                        if appeal_2_reason != '':
                            self.modify_table.setItem(row_new, 5, QTableWidgetItem(self.username))

            print(need_modify_count)
            self.modify_count.setText("待修改：" + str(need_modify_count) + "个句子")
        if self.method == "审核模式":
            sql = "SELECT video_name,uid,check_result,check_reason,modify_1_name,modify_1_flag," \
                  "modify_2_name, modify_2_flag,appeal_1_reason,appeal_1_reply,appeal_2_reason,appeal_2_reply FROM " \
                  "check_modify where (check_name=%s and appeal_1_reason !=%s) OR (check_name=%s and appeal_2_reason !=%s)"
            values = (self.username, '', self.username, '')
            cursor.execute(sql, values)
            reply_res = cursor.fetchall()
            print(reply_res)
            need_deal_count = 0
            for i in range(len(reply_res)):
                video_name = reply_res[i][0]
                uid = reply_res[i][1]
                sql = "SELECT label_1_result,label_2_result FROM label_result where video_name=%s and uid=%s"
                values = (video_name, uid)
                cursor.execute(sql, values)
                modify_res = cursor.fetchone()
                if reply_res[i][2] == 'label_1':
                    check_result = modify_res[0]
                    print(check_result)
                elif reply_res[i][2] == 'label_2':
                    check_result = modify_res[1]
                    print(check_result)
                else:
                    check_result = reply_res[i][2]
                    print(check_result)
                check_reason = reply_res[i][3]
                modify_1_name = reply_res[i][4]
                modify_1_flag = reply_res[i][5]
                modify_2_name = reply_res[i][6]
                modify_2_flag = reply_res[i][7]
                appeal_1_reason = reply_res[i][8]
                appeal_1_reply = reply_res[i][9]
                appeal_2_reason = reply_res[i][10]
                appeal_2_reply = reply_res[i][11]
                # if (appeal_1_reason != '' and appeal_1_reply=='') or (appeal_2_reason != '' and appeal_1_reply==''):
                if appeal_1_reason != '' or appeal_2_reason != '':
                    need_deal_count += 1
                    row_new = self.modify_table.rowCount()  # 返回当前行数(尾部)
                    self.modify_table.insertRow(row_new)
                    self.modify_table.setItem(row_new, 0, QTableWidgetItem(video_name))
                    self.modify_table.setItem(row_new, 1, QTableWidgetItem(str(uid)))
                    self.modify_table.setItem(row_new, 2, QTableWidgetItem("未通过，建议修改为:" + check_result))
                    self.modify_table.setItem(row_new, 3, QTableWidgetItem(check_reason))
                    self.modify_table.setItem(row_new, 4, QTableWidgetItem(appeal_1_reason))
                    self.modify_table.setItem(row_new, 5, QTableWidgetItem(modify_1_name))
                    self.modify_table.setItem(row_new, 6, QTableWidgetItem(appeal_1_reply))
                    self.modify_table.resizeColumnsToContents()
                if appeal_1_reason != '' and appeal_2_reason != '':
                    need_deal_count += 2
                    row_new = self.modify_table.rowCount()  # 返回当前行数(尾部)
                    self.modify_table.insertRow(row_new)
                    self.modify_table.setItem(row_new, 0, QTableWidgetItem(video_name))
                    self.modify_table.setItem(row_new, 1, QTableWidgetItem(str(uid)))
                    self.modify_table.setItem(row_new, 2, QTableWidgetItem("未通过，建议修改为:" + check_result))
                    self.modify_table.setItem(row_new, 3, QTableWidgetItem(check_reason))
                    self.modify_table.setItem(row_new, 4, QTableWidgetItem(appeal_1_reason))
                    self.modify_table.setItem(row_new, 5, QTableWidgetItem(modify_1_name))
                    self.modify_table.setItem(row_new, 6, QTableWidgetItem(appeal_1_reply))

                    row_new = self.modify_table.rowCount()  # 返回当前行数(尾部)
                    self.modify_table.insertRow(row_new)
                    self.modify_table.setItem(row_new, 0, QTableWidgetItem(video_name))
                    self.modify_table.setItem(row_new, 1, QTableWidgetItem(str(uid)))
                    self.modify_table.setItem(row_new, 2, QTableWidgetItem("未通过，建议修改为:" + check_result))
                    self.modify_table.setItem(row_new, 3, QTableWidgetItem(check_reason))
                    self.modify_table.setItem(row_new, 4, QTableWidgetItem(appeal_2_reason))
                    self.modify_table.setItem(row_new, 5, QTableWidgetItem(modify_2_name))
                    self.modify_table.setItem(row_new, 6, QTableWidgetItem(appeal_2_reply))
                    self.modify_table.resizeColumnsToContents()
            self.modify_count.setText("共：" + str(need_deal_count) + "个句子")

    def test(self):
        print("test success!")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # ui = LabelWin()
    ui = LoginWin()
    ui.show()
    sys.exit(app.exec_())
