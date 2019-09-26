import sys
import collections

import deltachat
import deltachat.message
from PyQt5.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout, QLineEdit, QTextEdit, QWidget, QListWidget, QListWidgetItem
from PyQt5.QtCore import QThread, QObject, pyqtSignal, pyqtSlot, pyqtRemoveInputHook, Qt


class EventConsumer(QObject):

    got_event = pyqtSignal(str, object, object)  # name, data1, data2

    def __init__(self, account, parent=None):
        super().__init__(parent)
        self._account = account

    def loop(self):
        while True:
            ev = self._account._evlogger.get()
            self.got_event.emit(*ev)


class EventHandler(QObject):

    incoming_message = pyqtSignal(deltachat.message.Message)

    def __init__(self, account, parent=None):
        super().__init__(parent)
        self._account = account

    @pyqtSlot(str, object, object)
    def dispatch(self, name, data1, data2):
        attr_name = 'on_' + name.replace('DC_EVENT_', '').lower()
        meth = getattr(self, attr_name, None)
        if meth is not None:
            meth(data1, data2)

    def on_incoming_msg(self, chat_id, msg_id):
        message = self._account.get_message_by_id(msg_id)
        self.incoming_message.emit(message)


def init_dc(app, addr, mail_pw):
    account = deltachat.Account("/tmp/delta.db")

    thread = QThread(parent=app)
    consumer = EventConsumer(account)
    consumer.moveToThread(thread)
    thread.started.connect(consumer.loop)
    thread.start()

    handler = EventHandler(account, parent=app)
    consumer.got_event.connect(handler.dispatch)

    account.start_threads(mvbox=True)
    if not account.is_configured():
        account.configure(addr=addr, mail_pw=mail_pw)
        # FIXME wait until configuration is done

    return handler, account


class MainWindow(QWidget):

    def __init__(self, account, parent=None):
        super().__init__(parent)
        self._account = account

        self._hbox = QHBoxLayout(self)
        self._vbox = QVBoxLayout(self)

        self._text_edit = QTextEdit()
        self._text_edit.setReadOnly(True)
        self._vbox.addWidget(self._text_edit)

        self._line_edit = QLineEdit()
        self._line_edit.editingFinished.connect(self.on_editing_finished)
        self._vbox.addWidget(self._line_edit)

        self._chat_list = QListWidget()
        self._init_chat_list()
        self._chat_list.currentItemChanged.connect(self._on_chatlist_item_changed)
        self._chat = None

        self._hbox.addWidget(self._chat_list)
        self._hbox.addLayout(self._vbox, 1)

    def _init_chat_list(self):
        for chat in self._account.get_chats():
            item = QListWidgetItem(chat.get_name())
            item.setData(Qt.UserRole, chat)
            self._chat_list.addItem(item)

    @pyqtSlot(QListWidgetItem)
    def _on_chatlist_item_changed(self, new):
        self._text_edit.clear()
        self._chat = new.data(Qt.UserRole)
        for message in self._chat.get_messages():
            self.on_incoming_message(message)

    def _display(self, user, text):
        self._text_edit.insertPlainText(f'\n<{user}> {text}')

    def _display_image(self, filename):
        self._text_edit.insertHtml(f'<img src="{filename}" width="100"></img>')

    def _scroll_to_bottom(self):
        bar = self._text_edit.verticalScrollBar()
        bar.setValue(bar.maximum())

    @pyqtSlot(deltachat.message.Message)
    def on_incoming_message(self, message):
        contact = message.get_sender_contact()
        if message.chat == self._chat:
            if message.is_image():
                self._display(contact.addr, message.text)
                self._display_image(message.filename)
            else:
                self._display(contact.addr, message.text)

            self._scroll_to_bottom()
            self._account.mark_seen_messages([message])

    @pyqtSlot()
    def on_editing_finished(self):
        text = self._line_edit.text()
        if not text:
            return
        self._line_edit.clear()
        self._display(self._account.get_self_contact().addr, text)
        self._chat.send_text(text)


def main():
    pyqtRemoveInputHook()
    app = QApplication(sys.argv)
    handler, account = init_dc(app, addr=sys.argv[1], mail_pw=sys.argv[2])

    window = MainWindow(account)
    handler.incoming_message.connect(window.on_incoming_message)
    window.show()

    app.exec_()


if __name__ == '__main__':
    main()
