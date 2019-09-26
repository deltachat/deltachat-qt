import sys
import collections

import deltachat
import deltachat.message
from PyQt5.QtWidgets import QApplication, QVBoxLayout, QLineEdit, QTextEdit, QWidget
from PyQt5.QtCore import QThread, QObject, pyqtSignal, pyqtSlot, pyqtRemoveInputHook


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
        self._vbox = QVBoxLayout(self)

        self._text_edit = QTextEdit()
        self._text_edit.setReadOnly(True)
        self._vbox.addWidget(self._text_edit)

        self._line_edit = QLineEdit()
        self._line_edit.editingFinished.connect(self.on_editing_finished)
        self._vbox.addWidget(self._line_edit)

        # addr = "t2@testrun.org"
        addr = "holger@deltachat.de"
        self._contact = self._account.create_contact(addr)
        self._chat = self._account.create_chat_by_contact(self._contact)
        for message in self._chat.get_messages():
            self.on_incoming_message(message)

    def _display(self, user, text):
        self._text_edit.insertPlainText(f'\n<{user}> {text}')

    @pyqtSlot(deltachat.message.Message)
    def on_incoming_message(self, message):
        contact = message.get_sender_contact()
        self._display(contact.addr, message.text)

    @pyqtSlot()
    def on_editing_finished(self):
        text = self._line_edit.text()
        if not text:
            return
        self._line_edit.clear()
        self._display('me', text)
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
