#!/usr/bin/env python
"""Configuration input panel for Arctic.

This is just a placeholder.

History:
2015-07-31 CS       Created
"""
import Tkinter
import RO.Constants
import RO.MathUtil
import RO.Wdg
import RO.KeyVariable
import TUI.TUIModel
import ArcticModel

_MaxDataWidth = 5

class StatusConfigInputWdg (RO.Wdg.InputContFrame):
    InstName = "Arctic"
    HelpPrefix = 'Instruments/%s/%sWin.html#' % (InstName, InstName)

    # category names
    CCDCat = "ccd"
    ConfigCat = RO.Wdg.StatusConfigGridder.ConfigCat

    def __init__(self,
        master,
        stateTracker,
    **kargs):
        """Create a new widget to show status for and configure Arctic

        Inputs:
        - master: parent widget
        - stateTracker: an RO.Wdg.StateTracker
        """
        RO.Wdg.InputContFrame.__init__(self, master=master, stateTracker=stateTracker, **kargs)
        self.model = ArcticModel.getModel()
        self.tuiModel = TUI.TUIModel.getModel()

        # set while updating user ccd binning or user window default,
        # to prevent storing new unbinned values for ccd window.
        self._freezeCCDUBWindow = False

        gr = RO.Wdg.StatusConfigGridder(
            master = self,
            sticky = "e",
        )
        self.gridder = gr

        shutterCurrWdg = RO.Wdg.StrLabel(self,
            helpText = "current state of the shutter",
            helpURL = self.HelpPrefix + "Shutter",
            anchor = "w",
        )
        self.model.shutter.addROWdg(shutterCurrWdg)
        gr.gridWdg ("Shutter", shutterCurrWdg, sticky="ew", colSpan=3)

        filterNameCurrWdg = RO.Wdg.StrLabel(self,
            helpText = "current filter",
            helpURL = self.HelpPrefix + "Filter",
            anchor = "w",
        )
        self.model.filterName.addROWdg(filterNameCurrWdg)
        self.filterNameUserWdg = RO.Wdg.OptionMenu(self,
            items=[],
            helpText = "requested filter",
            helpURL = self.HelpPrefix + "Filter",
            defMenu = "Current",
            autoIsCurrent = True,
        )
        gr.gridWdg (
            label = "Filter",
            dataWdg = filterNameCurrWdg,
            units = False,
            cfgWdg = self.filterNameUserWdg,
            sticky = "ew",
            cfgSticky = "w",
            colSpan = 3,
        )

        # amp readout
        ampNameCurrWdg = RO.Wdg.StrLabel(self,
            helpText = "current amp",
            helpURL = self.HelpPrefix + "Amp",
            anchor = "w",
        )
        self.model.ampName.addROWdg(ampNameCurrWdg)
        self.ampNameUserWdg = RO.Wdg.OptionMenu(self,
            items=[],
            helpText = "requested amp",
            helpURL = self.HelpPrefix + "Amp",
            defMenu = "Current",
            autoIsCurrent = True,
        )
        gr.gridWdg (
            label = "Amp",
            dataWdg = ampNameCurrWdg,
            units = False,
            cfgWdg = self.ampNameUserWdg,
            sticky = "ew",
            cfgSticky = "w",
            colSpan = 3,
        )


        # readout rate
        readoutRateNameCurrWdg = RO.Wdg.StrLabel(self,
            helpText = "current readout rate",
            helpURL = self.HelpPrefix + "Readout Rate",
            anchor = "w",
        )
        self.model.readoutRateName.addROWdg(readoutRateNameCurrWdg)
        self.readoutRateNameUserWdg = RO.Wdg.OptionMenu(self,
            items=[],
            helpText = "requested readoutRate",
            helpURL = self.HelpPrefix + "Readout Rate",
            defMenu = "Current",
            autoIsCurrent = True,
        )
        gr.gridWdg (
            label = "Readout Rate",
            dataWdg = readoutRateNameCurrWdg,
            units = False,
            cfgWdg = self.readoutRateNameUserWdg,
            sticky = "ew",
            cfgSticky = "w",
            colSpan = 3,
        )

        # ccd widgets

        # store user-set window in unbinned pixels
        # so the displayed binned value can be properly
        # updated when the user changes the binning
        self.userCCDUBWindow = None

        # ccd image header; the label is a toggle button
        # for showing ccd image info
        # grid that first as it is always displayed
        self.showCCDWdg = RO.Wdg.Checkbutton(self,
            text = "CCD",
            defValue = False,
            helpText = "Show binning, etc.?",
            helpURL = self.HelpPrefix + "ShowCCD",
        )
        gr.addShowHideControl(self.CCDCat, self.showCCDWdg)
        self._stateTracker.trackCheckbutton("showCCD", self.showCCDWdg)
        gr.gridWdg (
            label = self.showCCDWdg,
        )

        # grid ccd labels; these show/hide along with all other CCD data
        axisLabels = ("x", "y")
        ccdLabelDict = {}
        for setName in ("data", "cfg"):
            ccdLabelDict[setName] = [
                Tkinter.Label(self,
                    text=axis,
                )
                for axis in axisLabels
            ]
        gr.gridWdg (
            label = None,
            dataWdg = ccdLabelDict["data"],
            cfgWdg = ccdLabelDict["cfg"],
            sticky = "e",
            cat = self.CCDCat,
            row = -1,
        )

        ccdBinCurrWdgSet = [RO.Wdg.IntLabel(self,
            width = 4,
            helpText = "current bin factor in %s" % (axis,),
            helpURL=self.HelpPrefix + "Bin",
        )
            for axis in axisLabels
        ]
        self.model.ccdBin.addROWdgSet(ccdBinCurrWdgSet)

        self.ccdBinUserWdgSet = [
            RO.Wdg.IntEntry(self,
                minValue = 1,
                maxValue = 99,
                width = 2,
                helpText = "requested bin factor in %s" % (axis,),
                helpURL = self.HelpPrefix + "Bin",
                clearMenu = None,
                defMenu = "Current",
                callFunc = self._userBinChanged,
                autoIsCurrent = True,
            )
            for axis in axisLabels
        ]
        self.model.ccdBin.addROWdgSet(self.ccdBinUserWdgSet, setDefault=True)
        gr.gridWdg (
            label = "Bin",
            dataWdg = ccdBinCurrWdgSet,
            cfgWdg = self.ccdBinUserWdgSet,
            cat = self.CCDCat,
        )

        # CCD window

        winDescr = (
            "smallest x",
            "smallest y",
            "largest x",
            "largest y",
        )
        ccdWindowCurrWdgSet = [RO.Wdg.IntLabel(self,
            width = 4,
            helpText = "%s of current window (binned pix)" % winDescr[ii],
            helpURL = self.HelpPrefix + "Window",
        )
            for ii in range(4)
        ]
        self.model.ccdWindow.addROWdgSet(ccdWindowCurrWdgSet)

        self.ccdWindowUserWdgSet = [
            RO.Wdg.IntEntry(self,
                minValue = 1,
                maxValue = (2048, 2048, 2048, 2048)[ii],
                width = 4,
                helpText = "%s of requested window (binned pix)" % winDescr[ii],
                helpURL = self.HelpPrefix + "Window",
                clearMenu = None,
                defMenu = "Current",
                minMenu = ("Mininum", "Minimum", None, None)[ii],
                maxMenu = (None, None, "Maximum", "Maximum")[ii],
                callFunc = self._userWindowChanged,
                autoIsCurrent = True,
                isCurrent = False,
            ) for ii in range(4)
        ]
#       self.model.ccdUBWindow.addCallback(self._setCCDWindowWdgDef)
        gr.gridWdg (
            label = "Window",
            dataWdg = ccdWindowCurrWdgSet[0:2],
            cfgWdg = self.ccdWindowUserWdgSet[0:2],
            units = "LL bpix",
            cat = self.CCDCat,
        )
        gr.gridWdg (
            label = None,
            dataWdg = ccdWindowCurrWdgSet[2:4],
            cfgWdg = self.ccdWindowUserWdgSet[2:4],
            units = "UR bpix",
            cat = self.CCDCat,
        )

        # Image size, in binned pixels
        self.ccdImageSizeCurrWdgSet = [RO.Wdg.IntLabel(self,
            width = 4,
            helpText = "current %s size of image (binned pix)" % winDescr[ii],
            helpURL = self.HelpPrefix + "Window",
        )
            for ii in range(2)
        ]
#       self.model.ccdWindow.addCallback(self._updCurrImageSize)

        self.ccdImageSizeUserWdgSet = [
            RO.Wdg.IntLabel(self,
                width = 4,
                helpText = "requested %s size of image (binned pix)" % ("x", "y")[ii],
                helpURL = self.HelpPrefix + "ImageSize",
            ) for ii in range(2)
        ]
        gr.gridWdg (
            label = "Image Size",
            dataWdg = self.ccdImageSizeCurrWdgSet,
            cfgWdg = self.ccdImageSizeUserWdgSet,
            units = "bpix",
            cat = self.CCDCat,
        )

        # ccd overscan
        ccdOverscanCurrWdgSet = [RO.Wdg.IntLabel(self,
                width = 4,
                helpText = "current overscan in %s" % (axis,),
                helpURL = self.HelpPrefix + "Overscan",
            )
            for axis in axisLabels
        ]
        self.model.ccdOverscan.addROWdgSet(ccdOverscanCurrWdgSet)

        gr.gridWdg (
            label = "Overscan",
            dataWdg = ccdOverscanCurrWdgSet,
            units = "bpix",
            cat = self.CCDCat,
        )

        # set up format functions for the various pop-up menus
        # these allow us to return index values instead of names
        class indFormat(object):
            def __init__(self, indFunc, offset=1):
                self.indFunc = indFunc
                self.offset = offset
            def __call__(self, inputCont):
                valueList = inputCont.getValueList()
                if not valueList:
                    return ''
                name = inputCont.getName()
                return "%s %d" % (name, self.indFunc(valueList[0]) + self.offset)

        # add callbacks that access widgets
        self.model.filterNames.addCallback(self.filterNameUserWdg.setItems)
        self.model.filterName.addIndexedCallback(self.filterNameUserWdg.setDefault, 0)
        self.model.ampNames.addCallback(self.ampNameUserWdg.setItems)
        self.model.ampName.addIndexedCallback(self.ampNameUserWdg.setDefault, 0)
        self.model.readoutRateNames.addCallback(self.readoutRateNameUserWdg.setItems)
        self.model.readoutRateName.addIndexedCallback(self.readoutRateNameUserWdg.setDefault, 0)
        self.model.ccdUBWindow.addCallback(self._setCCDWindowWdgDef)
        self.model.ccdWindow.addCallback(self._updCurrImageSize)

        # set up the input container set; this is what formats the commands
        # and allows saving and recalling commands
        self.inputCont = RO.InputCont.ContList (
            conts = [
                RO.InputCont.WdgCont (
                    name = "filter",
                    wdgs = self.filterNameUserWdg,
                    formatFunc = indFormat(self.filterNameUserWdg.index),
                ),
                RO.InputCont.WdgCont (
                    name = "amp",
                    wdgs = self.ampNameUserWdg,
                    # formatFunc = indFormat(self.ampNameUserWdg.index),
                ),
                RO.InputCont.WdgCont (
                    name = "readout",
                    wdgs = self.readoutRateNameUserWdg,
                    # formatFunc = indFormat(self.readoutRateNameUserWdg.index),
                ),
                RO.InputCont.WdgCont (
                    name = "bin",
                    wdgs = self.ccdBinUserWdgSet,
                    formatFunc = RO.InputCont.BasicFmt(
                        rejectBlanks = True,
                    ),
                ),
                RO.InputCont.WdgCont (
                    name = "window",
                    wdgs = self.ccdWindowUserWdgSet,
                    formatFunc = RO.InputCont.BasicFmt(
                        rejectBlanks = True,
                    ),
                ),
            ],
        )

        self.configWdg = RO.Wdg.InputContPresetsWdg(
            master = self,
            sysName = "%sConfig" % (self.InstName,),
            userPresetsDict = self.tuiModel.userPresetsDict,
            stdPresets = dict(),
            inputCont = self.inputCont,
            helpText = "use and manage named presets",
            helpURL = self.HelpPrefix + "Presets",
        )
        self.gridder.gridWdg(
            "Presets",
            cfgWdg = self.configWdg,
            colSpan = 2,
        )

        self.gridder.allGridded()

        def repaint(evt):
            self.restoreDefault()
        self.bind("<Map>", repaint)

    def _saveCCDUBWindow(self):
        """Save user ccd window in unbinned pixels.
        """
        if self._freezeCCDUBWindow:
            return

        userWindow = [wdg.getNum() for wdg in self.ccdWindowUserWdgSet]
        if 0 in userWindow:
            return
        userBinFac = self._getUserBinFac()
        if 0 in userBinFac:
            return
        self.userCCDUBWindow = self.model.unbin(userWindow, userBinFac)

    def _setCCDWindowWdgDef(self, *args, **kargs):
        """Updates the default value of CCD window wdg.
        If this has the effect of changing the displayed values
        (only true if a box is blank) then update the saved unbinned window.
        """
        if self.userCCDUBWindow == None:
            currUBWindow, isCurrent = self.model.ccdUBWindow.get()
            if isCurrent:
                self.userCCDUBWindow = currUBWindow

        initialUserCCDWindow = self._getUserCCDWindow()
#       print "_setCCDWindowWdgDef; initialUserCCDWindow =", initialUserCCDWindow
        self._updUserCCDWindow(doCurrValue=False)
        if initialUserCCDWindow != self._getUserCCDWindow():
#           print "_setCCDWindowWdgDef; user value changed when default changed; save new unbinned value"
            self._saveCCDUBWindow()

    def _userBinChanged(self, *args, **kargs):
        """User bin factor changed.
        Update ccd window current values and default values.
        """
        self._updUserCCDWindow()

    def _userWindowChanged(self, *args, **kargs):
        self._saveCCDUBWindow()

        # update user ccd image size
        actUserCCDWindow = self._getUserCCDWindow()
        if 0 in actUserCCDWindow:
            return
        for ind in range(2):
            imSize = 1 + actUserCCDWindow[ind+2] - actUserCCDWindow[ind]
            self.ccdImageSizeUserWdgSet[ind].set(imSize)


    def _updCurrImageSize(self, *args, **kargs):
        """Updates current image size.
        """
        window, isCurrent = self.model.ccdWindow.get()
        if not isCurrent:
            return

        try:
            imageSize = [1 + window[ind+2] - window[ind] for ind in range(2)]
        except TypeError:
            imageSize = (None, None)

        for ind in range(2):
            self.ccdImageSizeCurrWdgSet[ind].set(imageSize[ind])

    def _updUserCCDWindow(self, doCurrValue = True):
        """Update user-set ccd window.

        Inputs:
        - doCurrValue: if True, set current value and default;
            otherwise just set default.

        The current value is set from the cached user's unbinned value
        """
        self._freezeCCDUBWindow = True
        try:
            if doCurrValue and self.userCCDUBWindow == None:
#               print "_updUserCCDWindow; unbinned = none"
                return
            userBinFac = self._getUserBinFac()
#           print "_updUserCCDWindow; userBinFac =", userBinFac
            if 0 in userBinFac:
#               print "_updUserCCDWindow; bin fac has 0"
                return

            # update user ccd window displayed value, default valud and limits
            if doCurrValue:
                userWindow = self.model.bin(self.userCCDUBWindow, userBinFac)
            currUBWindow, isCurrent = self.model.ccdUBWindow.get()
            if isCurrent:
                currWindow = self.model.bin(currUBWindow, userBinFac)
            else:
                currWindow = (None,)*4
#           print "_updUserCCDWindow; currWindow=", currWindow
            minWindowXYXY = self.model.minCoord(userBinFac)*2
            maxWindowXYXY = self.model.maxCoord(userBinFac)*2
#           print "_updUserCCDWindow: setting values", userWindow
            for ind in range(4):
                wdg = self.ccdWindowUserWdgSet[ind]

                # disable limits
                wdg.setRange(
                    minValue = None,
                    maxValue = None,
                )

                # set displayed and default value
                if doCurrValue:
                    wdg.set(userWindow[ind], isCurrent)
                wdg.setDefault(currWindow[ind], isCurrent)

                # set correct range for this bin factor
                wdg.setRange(
                    minValue = minWindowXYXY[ind],
                    maxValue = maxWindowXYXY[ind],
                )

        finally:
            self._freezeCCDUBWindow = False

    def _getUserBinFac(self):
        """Return the current user-set bin factor in x and y.
        """
        return [wdg.getNum() for wdg in self.ccdBinUserWdgSet]

    def _getUserCCDWindow(self):
        """Return the current user-set ccd window (binned) in x and y.
        """
        return [wdg.getNum() for wdg in self.ccdWindowUserWdgSet]


if __name__ == "__main__":
    import TestData
    root = TestData.tuiModel.tkRoot
    stateTracker = RO.Wdg.StateTracker(logFunc=TestData.tuiModel.logFunc)

    testFrame = StatusConfigInputWdg(root, stateTracker=stateTracker)
    testFrame.pack()

    TestData.start()

    testFrame.restoreDefault()

    def printCmds():
        cmdList = testFrame.getStringList()
        for cmd in cmdList:
            print cmd

    bf = Tkinter.Frame(root)
    cfgWdg = RO.Wdg.Checkbutton(bf, text="Config", defValue=True)
    cfgWdg.pack(side="left")
    Tkinter.Button(bf, text="Cmds", command=printCmds).pack(side="left")
    Tkinter.Button(bf, text="Current", command=testFrame.restoreDefault).pack(side="left")
    Tkinter.Button(bf, text="Demo", command=TestData.animate).pack(side="left")
    bf.pack()

    testFrame.gridder.addShowHideControl(testFrame.ConfigCat, cfgWdg)

    root.mainloop()
