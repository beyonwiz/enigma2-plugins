from __future__ import print_function

#pragma mark - GUI

#pragma mark Screens
from Screens.Screen import Screen
from Screens.HelpMenu import HelpableScreen
from Screens.MessageBox import MessageBox

#pragma mark Components
from Components.ActionMap import HelpableActionMap
from Components.AVSwitch import AVSwitch
from Components.Label import Label
from Components.Pixmap import Pixmap, MovingPixmap
from Components.Sources.StaticText import StaticText
from Components.Sources.List import List

#pragma mark Configuration
from Components.config import config

#pragma mark Picasa
from .PicasaApi import PicasaApi
from TagStrip import strip_readable

from enigma import ePicLoad, ePythonMessagePump, getDesktop
from collections import deque

try:
	xrange = xrange
except NameError:
	xrange = range

our_print = lambda *args, **kwargs: print("[EcasaGui]", *args, **kwargs)

class EcasaPictureWall(Screen, HelpableScreen):
	"""Base class for so-called "picture walls"."""
	PICS_PER_PAGE = 15
	PICS_PER_ROW = 5
	skin = """<screen position="center,center" size="600,380">
		<ePixmap position="0,0" size="140,40" pixmap="skin_default/buttons/red.png" transparent="1" alphatest="on"/>
		<ePixmap position="140,0" size="140,40" pixmap="skin_default/buttons/green.png" transparent="1" alphatest="on"/>
		<ePixmap position="280,0" size="140,40" pixmap="skin_default/buttons/yellow.png" transparent="1" alphatest="on"/>
		<ePixmap position="420,0" size="140,40" pixmap="skin_default/buttons/blue.png" transparent="1" alphatest="on"/>
		<ePixmap position="565,10" size="35,25" pixmap="skin_default/buttons/key_menu.png" alphatest="on"/>
		<widget source="key_red" render="Label" position="0,0" zPosition="1" size="140,40" valign="center" halign="center" font="Regular;21" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-1,-1"/>
		<widget source="key_green" render="Label" position="140,0" zPosition="1" size="140,40" valign="center" halign="center" font="Regular;21" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-1,-1"/>
		<widget source="key_yellow" render="Label" position="280,0" zPosition="1" size="140,40" valign="center" halign="center" font="Regular;21" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-1,-1"/>
		<widget source="key_blue" render="Label" position="420,0" zPosition="1" size="140,40" valign="center" halign="center" font="Regular;21" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-1,-1"/>
		<widget name="waitingtext" position="100,179" size="400,22" valign="center" halign="center" font="Regular;22"/>
		<widget name="image0"  position="30,50"   size="90,90"/>
		<widget name="image1"  position="140,50"  size="90,90"/>
		<widget name="image2"  position="250,50"  size="90,90"/>
		<widget name="image3"  position="360,50"  size="90,90"/>
		<widget name="image4"  position="470,50"  size="90,90"/>
		<widget name="image5"  position="30,160"  size="90,90"/>
		<widget name="image6"  position="140,160" size="90,90"/>
		<widget name="image7"  position="250,160" size="90,90"/>
		<widget name="image8"  position="360,160" size="90,90"/>
		<widget name="image9"  position="470,160" size="90,90"/>
		<widget name="image10" position="30,270"  size="90,90"/>
		<widget name="image11" position="140,270" size="90,90"/>
		<widget name="image12" position="250,270" size="90,90"/>
		<widget name="image13" position="360,270" size="90,90"/>
		<widget name="image14" position="470,270" size="90,90"/>
		<!-- TODO: find/create :P -->
		<widget name="highlight" position="25,45" size="100,100"/>
		</screen>"""
	def __init__(self, session, api=None):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)

		if api is None:
			self.api = PicasaApi(
					config.plugins.ecasa.google_username.value,
					config.plugins.ecasa.google_password.value,
					config.plugins.ecasa.cache.value)
		else:
			self.api = api

		self["key_red"] = StaticText(_("Close"))
		self["key_green"] = StaticText(_("My Albums"))
		self["key_yellow"] = StaticText()
		self["key_blue"] = StaticText(_("Search"))
		for i in xrange(self.PICS_PER_PAGE):
			self['image%d' % i] = Pixmap()
			self['title%d' % i] = StaticText()
		self["highlight"] = MovingPixmap()
		self["waitingtext"] = Label(_("Please wait... Loading list..."))

		self["overviewActions"] = HelpableActionMap(self, "EcasaOverviewActions", {
			"up": self.up,
			"down": self.down,
			"left": self.left,
			"right": self.right,
			"nextPage": (self.nextPage, _("show next page")),
			"prevPage": (self.prevPage, _("show previous page")),
			"select": self.select,
			"exit":self.close,
			"albums":(self.albums, _("show your albums (if logged in)")),
			"search":(self.search, _("start a new search")),
			}, -1)

		self.offset = 0
		self.__highlighted = 0
		self.pictures = ()

		# thumbnail loader
		self.picload = ePicLoad()
		self.picload.PictureData.get().append(self.gotPicture)
		sc = AVSwitch().getFramebufferScale()
		self.picload.setPara((90, 90, sc[0], sc[1], False, 1, '#ff000000')) # TODO: hardcoded size is evil!
		self.currentphoto = None
		self.queue = deque()

	@property
	def highlighted(self):
		return self.__highlighted

	@highlighted.setter
	def highlighted(self, highlighted):
		our_print("setHighlighted", highlighted)
		self.__highlighted = highlighted
		origpos = self['image%d' % highlighted].getPosition()
		# TODO: hardcoded highlight offset is evil :P
		self["highlight"].moveTo(origpos[0]-5, origpos[1]-5, 1)
		self["highlight"].startMoving()

	def gotPicture(self, picInfo=None):
		our_print("picture decoded")
		ptr = self.picload.getData()
		if ptr is not None:
			idx = self.pictures.index(self.currentphoto)
			realIdx = idx - self.offset
			self['image%d' % realIdx].instance.setPixmap(ptr.__deref__())
		self.currentphoto = None
		self.maybeDecode()

	def maybeDecode(self):
		if self.currentphoto is not None: return
		try:
			filename, self.currentphoto = self.queue.pop()
		except IndexError:
			our_print("no queued photos")
			# no more pictures
			pass
		else:
			self.picload.startDecode(filename)

	def pictureDownloaded(self, tup):
		filename, photo = tup
		self.queue.append((filename, photo))
		self.maybeDecode()

	def pictureDownloadFailed(self, tup):
		error, photo = tup
		our_print("pictureDownloadFailed", error, photo)
		# TODO: indicate in gui

	def setup(self):
		our_print("setup")
		self["waitingtext"].hide()
		self.queue.clear()
		pictures = self.pictures
		for i in xrange(self.PICS_PER_PAGE):
			try:
				our_print("trying to initiate download of idx", i+self.offset)
				picture = pictures[i+self.offset]
				self.api.downloadThumbnail(picture).addCallbacks(self.pictureDownloaded, self.pictureDownloadFailed)
			except IndexError:
				# no more pictures
				# TODO: set invalid pic for remaining items
				our_print("no more pictures in setup")
				break
			except Exception as e:
				our_print("unexpected exception in setup:", e)

	def up(self):
		highlighted = (self.highlighted - self.PICS_PER_ROW) % self.PICS_PER_PAGE
		our_print("up. before:", self.highlighted, ", after:", highlighted)
		self.highlighted = highlighted
	def down(self):
		highlighted = (self.highlighted + self.PICS_PER_ROW) % self.PICS_PER_PAGE
		our_print("down. before:", self.highlighted, ", after:", highlighted)
		self.highlighted = highlighted
	def left(self):
		highlighted = (self.highlighted - 1) % self.PICS_PER_PAGE
		our_print("left. before:", self.highlighted, ", after:", highlighted)
		self.highlighted = highlighted
	def right(self):
		highlighted = (self.highlighted + 1) % self.PICS_PER_PAGE
		our_print("right. before:", self.highlighted, ", after:", highlighted)
		self.highlighted = highlighted
	def nextPage(self):
		our_print("nextPage")
		offset = self.offset + self.PICS_PER_PAGE
		if offset > len(self.pictures):
			self.offset = 0
		else:
			self.offset = offset
		self.setup()
	def prevPage(self):
		our_print("prevPage")
		offset = self.offset - self.PICS_PER_PAGE
		if offset < 0:
			Len = len(self.pictures)
			self.offset = Len - (Len % self.PICS_PER_PAGE)
		else:
			self.offset = offset
		self.setup()
	def select(self):
		try:
			photo = self.pictures[self.highlighted+self.offset]
		except IndexError:
			our_print("no such picture")
			# TODO: indicate in gui
		else:
			self.session.open(EcasaPicture, photo, api=self.api)
	def albums(self):
		self.session.open(EcasaAlbumview, self.api)
	def search(self):
		our_print("search")
		# TODO: open vkeyboard, start search with results in feedview

	def gotPictures(self, pictures):
		if not self.instance: return
		self.pictures = pictures
		self.setup()

	def errorPictures(self, error):
		if not self.instance: return
		our_print("errorPictures", error)
		self.session.open(
			MessageBox,
			_("Error downloading") + ': ' + error.message,
			type=MessageBox.TYPE_ERROR,
			timeout=3
		)

class EcasaOverview(EcasaPictureWall):
	"""Overview and supposed entry point of ecasa. Shows featured pictures on the "EcasaPictureWall"."""
	def __init__(self, session):
		EcasaPictureWall.__init__(self, session)
		self.skinName = ["EcasaOverview", "EcasaPictureWall"]
		thread = EcasaThread(self.api.getFeatured)
		thread.deferred.addCallbacks(self.gotPictures, self.errorPictures)
		thread.start()

class EcasaFeedview(EcasaPictureWall):
	"""Display a nonspecific feed."""
	def __init__(self, session, thread, api=None):
		EcasaPictureWall.__init__(self, session, api=api)
		self.skinName = ["EcasaFeedview", "EcasaPictureWall"]
		self['key_green'].text = ''
		thread.deferred.addCallbacks(self.gotPictures, self.errorPictures)
		thread.start()

	def albums(self):
		pass

class EcasaAlbumview(Screen, HelpableScreen):
	"""Displays albums."""
	skin = """<screen position="center,center" size="560,420">
		<ePixmap pixmap="skin_default/buttons/red.png" position="0,0" size="140,40" transparent="1" alphatest="on" />
		<ePixmap pixmap="skin_default/buttons/green.png" position="140,0" size="140,40" transparent="1" alphatest="on" />
		<ePixmap pixmap="skin_default/buttons/yellow.png" position="280,0" size="140,40" transparent="1" alphatest="on" />
		<ePixmap pixmap="skin_default/buttons/blue.png" position="420,0" size="140,40" transparent="1" alphatest="on" />
		<widget source="key_red" render="Label" position="0,0" zPosition="1" size="140,40" font="Regular;20" valign="center" halign="center" backgroundColor="#1f771f" transparent="1" />
		<widget source="key_green" render="Label" position="140,0" zPosition="1" size="140,40" font="Regular;20" valign="center" halign="center" backgroundColor="#1f771f" transparent="1" />
		<widget source="key_yellow" render="Label" position="280,0" zPosition="1" size="140,40" font="Regular;20" valign="center" halign="center" backgroundColor="#1f771f" transparent="1" />
		<widget source="key_blue" render="Label" position="420,0" zPosition="1" size="140,40" font="Regular;20" valign="center" halign="center" backgroundColor="#1f771f" transparent="1" />
		<widget source="list" render="Listbox" position="0,50" size="560,360" scrollbarMode="showAlways">
			<convert type="TemplatedMultiContent">
				{"template": [
						MultiContentEntryText(pos=(1,1), size=(540,22), text = 0, font = 0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER),
					],
				  "fonts": [gFont("Regular", 20)],
				  "itemHeight": 24
				 }
			</convert>
		</widget>
	</screen>"""
	def __init__(self, session, api, user='default'):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.api = api
		self.user = user

		self['list'] = List()
		self['key_red'] = StaticText(_("Close"))
		self['key_green'] = StaticText()
		self['key_yellow'] = StaticText()
		self['key_blue'] = StaticText()

		self["albumviewActions"] = HelpableActionMap(self, "EcasaAlbumviewActions", {
			"select":(self.select, _("show album")),
			"exit":(self.close, _("Close")),
		}, -1)

		self.acquireAlbumsForUser(user)
		self.onLayoutFinish.append(self.layoutFinished)

	def layoutFinished(self):
		self.setTitle(_("eCasa: Albums for user %s") % (self.user,))

	def acquireAlbumsForUser(self, user):
		thread = EcasaThread(lambda:self.api.getAlbums(user=user))
		thread.deferred.addCallbacks(self.gotAlbums, self.errorAlbums)
		thread.start()

	def gotAlbums(self, albums):
		if not self.instance: return
		self['list'].list = albums

	def errorAlbums(self, error):
		if not self.instance: return
		our_print("errorAlbums", error)
		self['list'].setList([(_("Error downloading"), "0", None)])
		self.session.open(
			MessageBox,
			_("Error downloading") + ': ' + error.value.message,
			type=MessageBox.TYPE_ERROR,
			timeout=30,
		)

	def select(self):
		cur = self['list'].getCurrent()
		if cur:
			album = cur[-1]
			thread = EcasaThread(lambda:self.api.getAlbum(album))
			self.session.open(EcasaFeedview, thread, api=self.api)

class EcasaPicture(Screen, HelpableScreen):
	"""Display a single picture and its metadata."""
	PAGE_PICTURE = 0
	PAGE_INFO = 1
	def __init__(self, session, photo, api=None):
		size_w = getDesktop(0).size().width()
		size_h = getDesktop(0).size().height()
		self.skin = """<screen position="0,0" size="{size_w},{size_h}" title="{title}" flags="wfNoBorder">
			<widget name="pixmap" position="0,0" size="{size_w},{size_h}" backgroundColor="black" zPosition="2"/>
			<widget source="title" render="Label" position="25,20" zPosition="1" size="{labelwidth},40" valign="center" halign="left" font="Regular;21" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-1,-1"/>
			<widget source="summary" render="Label" position="25,60" zPosition="1" size="{labelwidth},100" valign="top" halign="left" font="Regular;21" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-1,-1"/>
			<widget source="keywords" render="Label" position="25,160" zPosition="1" size="{labelwidth},40" valign="center" halign="left" font="Regular;21" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-1,-1"/>
			<widget source="camera" render="Label" position="25,180" zPosition="1" size="{labelwidth},40" valign="center" halign="left" font="Regular;21" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-1,-1"/>
		</screen>""".format(size_w=size_w,size_h=size_h,title=(photo.title.text or '').encode('utf-8'), labelwidth=size_w-50)
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)

		self.photo = photo
		self.page = self.PAGE_PICTURE

		self['pixmap'] = Pixmap()

		unk = _("unknown")

		# camera
		if photo.exif.make and photo.exif.model:
			camera = '%s %s' % (photo.exif.make.text, photo.exif.model.text)
		elif photo.exif.make:
			camera = photo.exif.make.text
		elif photo.exif.model:
			camera = photo.exif.model.text
		else:
			camera = unk
		self['camera'] = StaticText(_("Camera: %s") % (camera,))

		title = photo.title.text if photo.title.text else unk
		self['title'] = StaticText(_("Title: %s") % (title,))
		summary = strip_readable(photo.summary.text) if photo.summary.text else unk
		self['summary'] = StaticText(_("Summary: %s") % (summary,))
		if photo.media and photo.media.keywords.text:
			keywords = photo.media.keywords.text
			# TODO: find a better way to handle this
			if len(keywords) > 50:
				keywords = keywords[:47] + "..."
		else:
			keywords = unk
		self['keywords'] = StaticText(_("Keywords: %s") % (keywords,))

		self["pictureActions"] = HelpableActionMap(self, "EcasaPictureActions", {
			"info": (self.info, _("show metadata")),
			"exit": (self.close, _("Close")),
			}, -1)

		try:
			real_w = int(photo.media.content[0].width.text)
			real_h = int(photo.media.content[0].heigth.text)
		except Exception as e:
			our_print("EcasaPicture.__init__: illegal w/h values, using max size!")
			real_w = size_w
			real_h = size_h

		self.picload = ePicLoad()
		self.picload.PictureData.get().append(self.gotPicture)
		sc = AVSwitch().getFramebufferScale()
		self.picload.setPara((real_w, real_h, sc[0], sc[1], False, 1, '#ff000000'))

		# NOTE: no need to start an extra thread for this, twisted is "parallel" enough in this case
		api.downloadPhoto(photo).addCallbacks(self.cbDownload, self.ebDownload)

	def gotPicture(self, picInfo=None):
		our_print("picture decoded")
		ptr = self.picload.getData()
		if ptr is not None:
			self['pixmap'].instance.setPixmap(ptr.__deref__())

	def cbDownload(self, tup):
		if not self.instance: return
		filename, photo = tup
		self.picload.startDecode(filename)

	def ebDownload(self, tup):
		if not self.instance: return
		error, photo = tup
		print("ebDownload", error)
		self.session.open(
			MessageBox,
			_("Error downloading") + ': ' + error.message,
			type=MessageBox.TYPE_ERROR,
			timeout=3
		)

	def info(self):
		our_print("info")
		if self.page == self.PAGE_PICTURE:
			self.page = self.PAGE_INFO
			self['pixmap'].hide()
		else:
			self.page = self.PAGE_PICTURE
			self['pixmap'].show()

#pragma mark - Thread

import threading
from twisted.internet import defer

class EcasaThread(threading.Thread):
	def __init__(self, fnc):
		threading.Thread.__init__(self)
		self.deferred = defer.Deferred()
		self.__pump = ePythonMessagePump()
		self.__pump.recv_msg.get().append(self.gotThreadMsg)
		self.__asyncFunc = fnc
		self.__result = None
		self.__err = None

	def gotThreadMsg(self, msg):
		if self.__err:
			self.deferred.errback(self.__err)
		else:
			try:
				self.deferred.callback(self.__result)
			except Exception as e:
				self.deferred.errback(e)

	def run(self):
		try:
			self.__result = self.__asyncFunc()
		except Exception as e:
			self.__err = e
		finally:
			self.__pump.send(0)