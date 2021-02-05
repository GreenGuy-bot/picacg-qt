import json
import weakref

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import QRect, Qt
from PyQt5.QtGui import QPixmap, QColor
from PyQt5.QtWidgets import QListWidget, QListWidgetItem, QWidget, QVBoxLayout, QLabel, QHBoxLayout, QAbstractSlider, \
    QApplication

from conf import config
from resources import resources
from src.index.book import BookMgr
from src.qt.qtbubblelabel import QtBubbleLabel
from src.qt.qtlistwidget import QtBookList
from src.qt.qtloading import QtLoading
from src.qt.qtreadimg import QtReadImg
from src.server import req, Log, Server, QtTask
from src.user.user import User
from src.util.status import Status
from ui.bookinfo import Ui_BookInfo


class QtBookInfo(QtWidgets.QDialog, Ui_BookInfo):
    def __init__(self, owner):
        super(self.__class__, self).__init__()
        Ui_BookInfo.__init__(self)
        self.setupUi(self)
        self.owner = weakref.ref(owner)
        self.loadingForm = QtLoading(self)
        self.bookId = ""
        self.url = ""
        self.path = ""
        self.bookName = ""
        self.lastEpsId = -1

        self.msgForm = QtBubbleLabel(self)
        self.title.setGeometry(QRect(328, 240, 329, 27 * 4))
        self.title.setWordWrap(True)
        self.title.setAlignment(Qt.AlignTop)
        self.title.setContextMenuPolicy(Qt.CustomContextMenu)
        self.title.customContextMenuRequested.connect(self.CopyTitle)
        self.autor.setContextMenuPolicy(Qt.CustomContextMenu)
        self.autor.customContextMenuRequested.connect(self.CopyAutor)
        self.description.setContextMenuPolicy(Qt.CustomContextMenu)
        self.description.customContextMenuRequested.connect(self.CopyDescription)

        self.description.setGeometry(QRect(328, 240, 329, 27 * 4))
        self.description.setWordWrap(True)
        self.description.setAlignment(Qt.AlignTop)

        self.categories.setGeometry(QRect(328, 240, 329, 27 * 4))
        self.categories.setWordWrap(True)
        self.categories.setAlignment(Qt.AlignTop)

        self.tags.setGeometry(QRect(328, 240, 329, 27 * 4))
        self.tags.setWordWrap(True)
        self.tags.setAlignment(Qt.AlignTop)

        self.epsListWidget = QListWidget(self)
        self.epsListWidget.setFlow(self.epsListWidget.LeftToRight)
        self.epsListWidget.setWrapping(True)
        self.epsListWidget.setFrameShape(self.epsListWidget.NoFrame)
        self.epsListWidget.setResizeMode(self.epsListWidget.Adjust)

        self.epsLayout.addWidget(self.epsListWidget)

        self.listWidget = QtBookList(self, self.__class__.__name__)
        self.listWidget.InitUser(self.LoadNextPage)

        self.commentLayout.addWidget(self.listWidget)

        self.qtReadImg = QtReadImg(self, owner)
        self.stackedWidget.addWidget(self.qtReadImg)
        self.epsListWidget.clicked.connect(self.OpenReadImg)

        self.closeFlag = self.__class__.__name__ + "-close"         # 切换book时，取消加载

    def closeEvent(self, a0: QtGui.QCloseEvent) -> None:
        if self.stackedWidget.currentIndex() == 1:
            self.stackedWidget.setCurrentIndex(0)
            self.qtReadImg.AddHistory()
            self.LoadHistory()
            a0.ignore()
        else:
            a0.accept()

    def CopyTitle(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.title.text())
        self.msgForm.ShowMsg("复制标题")
        return

    def CopyAutor(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.autor.text())
        self.msgForm.ShowMsg("复制作者")
        return

    def CopyDescription(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.description.text())
        self.msgForm.ShowMsg("复制描述")
        return

    def OpenBook(self, bookId):
        self.bookId = bookId
        self.setWindowTitle(self.bookId)
        if self.bookId in self.owner().downloadForm.downloadDict:
            self.download.setEnabled(False)
        else:
            self.download.setEnabled(True)

        self.owner().qtTask.CancelTasks(self.closeFlag)
        self.stackedWidget.setCurrentIndex(0)
        self.show()
        self.loadingForm.show()
        self.owner().qtTask.AddHttpTask(lambda x: BookMgr().AddBookById(bookId, x), self.OpenBookBack)

    def close(self):
        super(self.__class__, self).close()

    def OpenBookBack(self, msg):
        self.loadingForm.close()
        self.listWidget.clear()
        self.listWidget.UpdatePage(1, 1)
        self.listWidget.UpdateState()
        info = BookMgr().books.get(self.bookId)
        if msg == Status.Ok and info:
            self.autor.setText("作者：" + info.author)
            self.title.setText("标题：" + info.title)
            self.bookName = info.title
            self.description.setText("描述：" + info.description)
            self.isFinished.setText("完本" if info.finished else "未完本")
            self.categories.setText("分类：" + ','.join(info.categories))
            self.tags.setText("TAG：" + ','.join(info.tags))
            self.likes.setText("爱心数：" + str(info.totalLikes))
            self.views.setText("观看数：" + str(info.totalViews))

            if info.isFavourite:
                self.favorites.setEnabled(False)
            else:
                self.favorites.setEnabled(True)
            self.picture.setText("图片加载中...")
            fileServer = info.thumb.get("fileServer")
            path = info.thumb.get("path")
            name = info.thumb.get("originalName")
            self.url = fileServer
            self.path = path
            if config.IsLoadingPicture:

                self.owner().qtTask.AddDownloadTask(fileServer, path, name, completeCallBack=self.UpdatePicture, cleanFlag=self.closeFlag)
            self.owner().qtTask.AddHttpTask(lambda x: Server().Send(req.GetComments(self.bookId), bakParam=x),
                                            self.GetCommnetBack, cleanFlag=self.closeFlag)

            self.owner().qtTask.AddHttpTask(lambda x: BookMgr().AddBookEpsInfo(self.bookId, x), self.GetEpsBack, cleanFlag=self.closeFlag)
        else:
            # QtWidgets.QMessageBox.information(self, '加载失败', msg, QtWidgets.QMessageBox.Yes)
            self.msgForm.ShowError(msg)
            self.close()
        return

    def UpdatePicture(self, data, status):
        if status == Status.Ok:
            pic = QtGui.QPixmap()
            pic.loadFromData(data)
            pic.scaled(self.picture.size(), QtCore.Qt.KeepAspectRatio)
            self.picture.setPixmap(pic)
            # self.picture.setScaledContents(True)
            self.update()
        else:
            self.picture.setText("图片加载失败")
        return

    # 加载评论
    def GetCommnetBack(self, data):
        try:
            self.loadingForm.close()
            self.listWidget.UpdateState()
            msg = json.loads(data)
            if msg.get("code") == 200:
                comments = msg.get("data", {}).get("comments", {})
                page = int(comments.get("page", 1))
                pages = int(comments.get("pages", 1))
                limit = int(comments.get("limit", 1))
                self.listWidget.UpdatePage(page, pages)
                total = comments.get("total", 0)
                self.tabWidget.setTabText(1, "评论({})".format(str(total)))

                for index, info in enumerate(comments.get("docs")):
                    floor = total - ((page - 1) * limit + index)
                    content = info.get("content")
                    name = info.get("_user", {}).get("name")
                    avatar = info.get("_user", {}).get("avatar", {})
                    createdTime = info.get("created_at")
                    commentsCount = info.get("commentsCount")
                    self.listWidget.AddUserItem(content, name, createdTime, floor, avatar.get("fileServer"),
                                 avatar.get("path"), avatar.get("originalName"))
            return
        except Exception as es:
            import sys
            cur_tb = sys.exc_info()[2]  # return (exc_type, exc_value, traceback)
            e = sys.exc_info()[1]
            Log.Error(cur_tb, e)

    def GetEpsBack(self, st):
        if st == Status.Ok:
            self.UpdateEpsData()
            self.LoadHistory()
            return
        return

    def UpdateEpsData(self):
        self.epsListWidget.clear()
        info = BookMgr().books.get(self.bookId)
        if not info:
            return
        for epsInfo in info.eps:
            label = QLabel(epsInfo.title)
            label.setContentsMargins(20, 10, 20, 10)
            item = QListWidgetItem(self.epsListWidget)
            item.setSizeHint(label.sizeHint())
            self.epsListWidget.setItemWidget(item, label)
        return

    def AddDownload(self):
        if self.owner().downloadForm.AddDownload(self.bookId):
            self.owner().msgForm.ShowMsg("添加下载成功")
        else:
            self.owner().msgForm.ShowMsg("已在下载列表")
        self.download.setEnabled(False)

    def AddFavority(self):
        User().AddAndDelFavorites(self.bookId)
        self.owner().msgForm.ShowMsg("添加收藏成功")
        self.favorites.setEnabled(False)

    def LoadNextPage(self):
        self.loadingForm.show()
        self.owner().qtTask.AddHttpTask(
            lambda x: Server().Send(req.GetComments(self.bookId, self.listWidget.page + 1), bakParam=x),
            self.GetCommnetBack, cleanFlag=self.closeFlag)
        return

    def OpenReadImg(self, modelIndex):
        index = modelIndex.row()
        item = self.epsListWidget.item(index)
        if not item:
            return
        widget = self.epsListWidget.itemWidget(item)
        if not widget:
            return
        name = widget.text()
        self.qtReadImg.OpenPage(self.bookId, index, name)
        self.stackedWidget.setCurrentIndex(1)

    def LoadHistory(self):
        info = self.owner().historyForm.GetHistory(self.bookId)
        if not info:
            return
        if self.lastEpsId == info.epsId:
            return

        if self.lastEpsId >= 0:
            item = self.epsListWidget.item(self.lastEpsId)
            if item:
                item.setBackground(QColor(255, 255, 255))

        item = self.epsListWidget.item(info.epsId)
        if not item:
            return
        item.setBackground(QColor(238, 162, 164))
        self.epsListWidget.update()
        self.lastEpsId = info.epsId
