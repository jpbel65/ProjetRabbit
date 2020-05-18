from tkinter import *
from pafy import *
from vlc import *
from PIL import Image as PILImage, ImageTk
import asyncio
import websockets
import threading
import multiprocessing
import requests
import queue
import io


class App:
    def __init__(self, window, title, kq):
        self.videoOnly = False
        self.previewList = False
        self.kq = kq
        self.window = window
        window.bind('<Escape>', self.switch_view)
        window.bind('<Return>', self.create_request)
        self.window.title(title)
        self.window.attributes("-topmost", True)
        self.panel = None
        self.media = None
        self.player = None
        self.webSocket = None
        self.videoQueue = queue.Queue()

        self.videoFrame = LabelFrame(window)
        self.videoFrame.pack(fill="both", expand="yes", sid="left")
        self.optionFrame = LabelFrame(window, text="Option")
        self.optionFrame.pack(fill="both", expand="no", sid="right")

        self.toolsFrame = LabelFrame(self.optionFrame)
        self.toolsFrame.pack(fill="x", expand="no", sid="top")
        self.slider = Scale(self.toolsFrame, from_=0, to=100, orient=HORIZONTAL, command=lambda value: self.set_volume(value))
        self.currentTimer = Label(self.toolsFrame, text="00:00")
        self.totalTimer = Label(self.toolsFrame, text="/ 00:00")
        self.buttonFullScreen = Button(self.toolsFrame, command=lambda: self.switch_view('fullScreen'), text="FullScreen")
        self.buttonHide = Button(self.toolsFrame, command=lambda: self.switch_view('hide'), text="Hide")
        self.currentTimer.pack(sid="left")
        self.totalTimer.pack(sid="left")
        self.buttonFullScreen.pack(sid="left")
        self.buttonHide.pack(sid="left")
        self.slider.pack(sid="right")

        self.input = Entry(self.optionFrame)
        self.input.pack(fill="x", expand="no", sid="top")

        self.previewFrame = LabelFrame(self.optionFrame, text="Preview")
        self.previewFrame.pack(fill="x", expand="no", sid="top")

        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)

        t1 = threading.Thread(target=self.async_run_video)
        t2 = threading.Thread(target=self.async_run_comm_web)
        t3 = threading.Thread(target=self.get_video_time)
        t1.start()
        t2.start()
        t3.start()

    async def request_async(self):
        await self.webSocket.send(self.input.get())
        self.input.delete(0, 'end')

    def create_request(self, event):
        asyncio.new_event_loop().run_until_complete(self.request_async())

    def add_request(self, request):
        frame = LabelFrame(self.previewFrame)
        info_frame = Label(frame)
        info_frame.pack(sid="right")
        thumb_frame = Label(frame)
        thumb_frame.pack(sid="left")
        pafy_request = pafy.new(request)

        respond = requests.get(pafy_request.thumb).content
        data = PILImage.open(io.BytesIO(respond))
        image = ImageTk.PhotoImage(data)
        thumb = Label(thumb_frame, image=image)
        thumb.pack()

        titles = pafy_request.title.split()
        segment = []
        for i in range(4):
            element = ''
            while len(element) < 20 and titles:
                element += (titles.pop(0) + ' ')
            segment.append(element)
        for element in segment:
            Label(info_frame, text=element).pack()
        timer = Label(info_frame, text='Time : {}'.format(pafy_request.duration))
        timer.pack()
        frame.pack()
        self.videoQueue.put((request, frame, image))

    def switch_view(self, event):
        if self.videoOnly is True:
            self.window.attributes("-fullscreen", False)
            self.optionFrame.pack(fill="both", expand="no", sid="right")
            self.videoOnly = False
        elif event == 'fullScreen':
            self.window.attributes("-fullscreen", True)
            self.videoOnly = True
            self.optionFrame.pack_forget()
        elif event == 'hide':
            self.videoOnly = True
            self.optionFrame.pack_forget()

    def set_volume(self, value):
        if self.player is not None:
            self.player.audio_set_volume(int(value))

    def get_video_time(self):
        while True:
            if self.player is not None:
                time = int(int(libvlc_media_player_get_time(self.player)) / 1000)
                second = time % 60
                minute = int((time - second) / 60)
                self.currentTimer.configure(text='{0:0=2d}:{1:0=2d}'.format(minute, second))

    def get_video_length(self):
        time = int(int(libvlc_media_player_get_length(self.player)) / 1000)
        second = time % 60
        minute = int((time - second) / 60)
        return ' / {0:0=2d}:{1:0=2d}'.format(minute, second)

    async def video_run(self):
        while True:
            url, frame, image = self.videoQueue.get()
            if self.player is not None:
                self.panel.destroy()
            self.panel = Label(self.videoFrame)
            self.panel.pack(fill=BOTH, expand=1, sid="bottom")
            link_pafy = pafy.new(url)
            best_link_video = link_pafy.getbest()
            vlc_instance = Instance()
            self.player = vlc_instance.media_player_new()
            self.player.set_hwnd(self.panel.winfo_id())  # tkinter label or frame
            self.media = vlc_instance.media_new(best_link_video.url)
            self.media.get_mrl()
            self.player.set_media(self.media)
            self.player.audio_set_volume(20)
            self.slider.set(20)
            self.player.play()
            while self.player.get_state().value != 3:
                pass
            self.player.pause()
            self.totalTimer.configure(text=self.get_video_length())
            await self.webSocket.send("ready")
            while self.player.get_state().value != 6:
                pass
            frame.destroy()

    def on_closing(self):
        if self.player is not None:
            self.player.stop()
        self.kq.put(True)
        self.window.quit()
        self.window.destroy()

    def async_run_comm_web(self):
        asyncio.new_event_loop().run_until_complete(self.web_socket_canal())

    def async_run_video(self):
        asyncio.new_event_loop().run_until_complete(self.video_run())

    async def web_socket_canal(self):
        response = requests.get('https://afternoon-woodland-81509.herokuapp.com/')
        port = response.json()
        uri = "ws://afternoon-woodland-81509.herokuapp.com/"+port
        async with websockets.connect(uri, ping_interval=1, ping_timeout=None) as self.webSocket:
            while self.webSocket.closed is False:
                respond = await self.webSocket.recv()
                print(f"< {respond}")
                if respond == 'play':
                    if self.player is not None:
                        self.player.play()
                elif respond == 'stop':
                    if self.player is not None:
                        self.player.pause()
                else:
                    self.add_request(respond)


def start(kq):
    app = App(Tk(), "ProjetRabbit", kq)
    app.window.mainloop()


if __name__ == '__main__':
    multiprocessing.freeze_support()
    killQueue = multiprocessing.Queue()

    p = multiprocessing.Process(target=start, args=(killQueue,))
    p.start()
    while True:
        if killQueue.get() is True:
            p.kill()
            break

