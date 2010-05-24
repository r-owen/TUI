"""
TO DO: If a command has only one stage then do not show the stage checkbox
but still show the parameters for that stage.
"""
import itertools
import time
import Tkinter
import RO.Alg
import RO.Astro.Tm
import RO.PhysConst
import RO.AddCallback
import TUI.Models
import opscore.actor

StateWidth = 10
CommandNameWidth = 12
StageNameWidth = 10

class TimerWdg(Tkinter.Frame):
    """A thin wrapper around RO.Wdg.TimeBar that hides itself when necessary
    
    This is not needed for commands or stages. It *may* be wanted for parameters
    and is likely to be wanted for tasks (which will be handled in a different file).
    Meanwhile keep it around...
    """
    def __init__(self, master):
        Tkinter.Frame.__init__(master)
        self._timerWdg = RO.Wdg.TimeBar(
            master = self,
            countUp = False,
        )
        self._timerWdg.grid(row=0, column=0)
    
    def setTime(self, startTime=0, totDuration=0):
        """Run or hide the countdown timer
        
        Inputs:
        - startTime: predicted start time (TAI, MJD seconds); 0 = now
        - totDuration: total predicted duration of timer (sec); 0 = hide timer
        """
        if totDuration <= 0:
            self._timerWdg.grid_withdraw()
            self._timerWdg.clear()
        else:
            if startTime == 0:
                remTime = totDuration
            else:
                currTime = RO.Astro.Tm.taiFromPySec() * RO.PhysConst.SecPerDay
                remTime = currTime - startTime
            self._timerWdg.start(
                newMax = totDuration,
                value = remTime,
            )
            self._timerWdg.grid()

    def clear(self):
        """Clear and hide the timer widget
        """
        self.setTime(0, 0)


class CmdInfo(object):
    def __init__(self, cmdVar=None, wdg=None):
        self.cmdVar = cmdVar
        self.wdg = wdg
    
    def abort(self):
        if self.cmdVar:
            self.cmdVar.abort()

    @property
    def isDone(self):
        return (not self.cmdVar) or self.cmdVar.isDone

    @property
    def didFail(self):
        return (not self.cmdVar) or self.cmdVar.didFail

    @property
    def isRunning(self):
        return bool(self.cmdVar) and not self.cmdVar.isDone

    def disableIfRunning(self):
        if self.isRunning:
            self.wdg.setEnable(False)


class ItemState(RO.AddCallback.BaseMixin):
    """Keep track of the state of an item
    
    Callback functions are called when the state changes.
    """
    DoneStates = set(("aborted", "done", "failed", "idle", "off"))
    FailedStates = set(("aborted", "failed"))
    ErrorStates = FailedStates
    RunningStates = set(("starting", "prepping", "running"))
    DisabledStates = set(("off",))
    ValidStates = set((None,)) | DoneStates | FailedStates | ErrorStates | RunningStates | DisabledStates
    def __init__(self, name="", callFunc=None, callNow=False):
        """Constructor
        """
        self.name = name
        self.state = None
        RO.AddCallback.BaseMixin.__init__(self, callFunc=callFunc, callNow=callNow)

    @property
    def didFail(self):
        """Did this stage of the sop command fail?
        """
        return self.state in self.FailedStates

    @property
    def isDone(self):
        """Is this object finished (whether successfully or not)?
        """
        return self.state in self.DoneStates

    @property
    def isRunning(self):
        """Is this object running normally?
        """
        return self.state in self.RunningStates

    def _setState(self, state):
        """Set the state of this item
        
        Inputs:
        - state: desired state for object
        """
#        print "%s._setState(state=%r)" % (self, state)
        self.state = state

        self._doCallbacks()

    def __str__(self):
        return "State(name=%s, state=%s)" % (self.name, self.state)


class ItemStateWdgSet(ItemState, RO.AddCallback.BaseMixin):
    """Widget showing state of SOP command, stage, or parameter
    
    Subclasses must override:
    enableWdg
    and must grid or pack:
    self.stateWdg
    plus any other widgets it wants
    """
    def __init__(self, master, name, dispName, callFunc=None, helpURL=None):
        """Constructor
        
        Inputs:
        - master: master widget for stateWdg
        - name: name of command, stage or parameter as known by sop (full dotted notation)
        - dispName: displayed name (text for control widget); if None then use last field of name
        - callFunc: callback function for state changes
        - helpURL: URL of help file
        """
        ItemState.__init__(self, name=name, callFunc=self.enableWdg)
        RO.AddCallback.BaseMixin.__init__(self)

        self.name = name
        self.dispName = dispName
        self.helpURL = helpURL
        
        self.stateWdg = RO.Wdg.StrLabel(
            master = master,
            width = StateWidth,
            anchor = "w",
            helpText = "State of %s" % (self,),
            helpURL = self.helpURL,
        )

        if callFunc:
            self.addCallback(callFunc, callNow=False)

    def enableWdg(self, dumWdg=None):
        """Enable widget based on current state
        
        If only CommandWdg wants this, then probably better to make it
        a callback function that Command explicitly issues.
        """
        pass

    @property
    def isCurrent(self):
        """Does the state of the control widget match the state of the sop command?
        """
        raise RuntimeError("Must subclass")
        return self.controlWdg.getIsCurrent()

    @property
    def isDefault(self):
        """Is the control widget set to its default state?
        """
        raise RuntimeError("Must subclass")

    def setState(self, state, isCurrent=True):
        """Set the state of this item
        
        Inputs:
        - state: desired state for object
        - text: new text; if None then left unchanged
        
        @raise RuntimeError if called after state is done
        """
        ItemState._setState(self, state)

        if state in self.ErrorStates:
            severity = RO.Constants.sevError
        else:
            severity = RO.Constants.sevNormal

        
        if self.state == None:
            dispState = None
        else:
            dispState = self.state.title()
        self.stateWdg.set(dispState, severity = severity, isCurrent = isCurrent)
        
        self.enableWdg()

    def __str__(self):
        return "%s(%s)" % (type(self).__name__, self.dispName,)


class CommandWdg(ItemStateWdgSet, Tkinter.Frame):
    """SOP command widget
    """
    def __init__(self,
        master,
        commandDescr,
        statusBar,
        callFunc = None,
        helpURL = None,
    ):
        """Create a CommandWdg
        
        Inputs: same as ItemStateWdgSet plus:
        - commandDescr: a CommandDescr object describing the command and its stages and parameters
        - statusBar: status bar widget
        """
        Tkinter.Frame.__init__(self, master)
        ItemStateWdgSet.__init__(self,
            master = self,
            name = commandDescr.baseName,
            dispName = commandDescr.dispName,
            callFunc = callFunc,
            helpURL = helpURL,
        )
        self.statusBar = statusBar
        self.actor = commandDescr.actor
        # dictionary of known stages: stage base name: stage
        self.stageDict = dict()
        # ordered dictionary of visible stages: stage base name: stage
        self.visibleStageODict = RO.Alg.OrderedDict()
        self.currCmdInfo = CmdInfo()

        self.sopModel = TUI.Models.getModel("sop")
        
        self.stateWdg.grid(row=0, column=0, sticky="w")
        self.commandFrame = Tkinter.Frame(self)
        self.commandFrame.grid(row=0, column=1, columnspan=3, sticky="w")
        self._makeCmdWdg()
        
        self.stageFrame = Tkinter.Frame(self)
        self.stageFrame.grid(row=1, column=0, columnspan=2, sticky="w")
        self.paramFrame = Tkinter.Frame(self)
        self.paramFrame.grid(row=1, column=2, columnspan=2, sticky="w")
        self.grid_columnconfigure(3, weight=1)

        for stageDescr in commandDescr.descrList:
            stage = StageWdg(
                master = self.stageFrame,
                paramMaster = self.paramFrame,
                callFunc = self.enableWdg,
                stageDescr = stageDescr,
            )
            self.stageDict[stage.name] = stage

        # NOTE: the stages and their parameters are gridded in _commandStagesCallback

        commandStateKeyVar = getattr(self.sopModel, "%sState" % (self.name,))
        commandStateKeyVar.addCallback(self._commandStateCallback)
        commandStagesKeyVar = getattr(self.sopModel, "%sStages" % (self.name,))
        commandStagesKeyVar.addCallback(self._commandStagesCallback)

    def _makeCmdWdg(self):
        self.nameWdg = RO.Wdg.StrLabel(
            master = self.commandFrame,
            text = self.dispName,
            width = CommandNameWidth,
            anchor = "w",
            helpText = "%s command" % (self.name,),
            helpURL = self.helpURL,
        )
        self.nameWdg.pack(side="left")
        
        self.startBtn = RO.Wdg.Button(
            master = self.commandFrame,
            text = "Start",
            callFunc = self.doStart,
            helpText = "Start %s command" % (self.name,),
            helpURL = self.helpURL,
        )
        self.startBtn.pack(side="left")

        self.modifyBtn = RO.Wdg.Button(
            master = self.commandFrame,
            text = "Modify",
            callFunc = self.doStart,
            helpText = "Modify %s command" % (self.name,),
            helpURL = self.helpURL,
        )
        self.modifyBtn.pack(side="left")

        self.abortBtn = RO.Wdg.Button(
            master = self.commandFrame,
            text = "X",
            callFunc = self.doAbort,
            helpText = "Abort %s command" % (self.name,),
            helpURL = self.helpURL,
        )
        self.abortBtn.pack(side="left")
        
        self.currentBtn = RO.Wdg.Button(
            master = self.commandFrame,
            text = "Current",
            callFunc = self.restoreCurrent,
            helpText = "Restore current stages and parameters",
            helpURL = self.helpURL,
        )
        self.currentBtn.pack(side="left")
        
        self.defaultBtn = RO.Wdg.Button(
            master = self.commandFrame,
            text = "Default",
            callFunc = self.restoreDefault,
            helpText = "Restore default stages and parameters",
            helpURL = self.helpURL,
        )
        self.defaultBtn.pack(side="left")

    def doAbort(self, wdg=None):
        """Abort the command
        """
        if not self.currCmdInfo.isDone:
            self.currCmdInfo.abort()
        if not self.isRunning:
            cmdStr = "%s abort" % (self.name,),
            self.doCmd(cmdStr, wdg)

    def doStart(self, wdg=None):
        """Start or modify the command
        """
        self.doCmd(self.getCmdStr(), wdg)

    def doCmd(self, cmdStr, wdg=None, **keyArgs):
        """Run the specified command
        
        Inputs:
        - cmdStr: command string
        - wdg: widget that started the command (to disable it while the command runs)
        **keyArgs: all other keyword arguments are used to construct opscore.actor.keyvar.CmdVar
        """
        cmdVar = opscore.actor.keyvar.CmdVar(
            actor = self.actor,
            cmdStr = self.getCmdStr(),
            callFunc = self.enableWdg,
        **keyArgs)
        self.statusBar.doCmd(cmdVar)
        self.currCmdInfo = CmdInfo(cmdVar, wdg)
        self.enableWdg()

    def enableWdg(self, dumWdg=None):
        """Enable widgets according to current state
        """
        self.startBtn.setEnable(self.isDone)
        
        # can modify if not current and sop is running this command
        canModify = not self.isCurrent and self.isRunning
        self.modifyBtn.setEnable(canModify)

        # can abort this sop is running this command or if I have a running cmdVar for sop
        canAbort = self.isRunning or (not self.currCmdInfo.isDone)
        self.abortBtn.setEnable(canAbort)

        self.defaultBtn.setEnable(not self.isDefault)
        self.currentBtn.setEnable(not self.isCurrent)
        self.currCmdInfo.disableIfRunning()

    def getCmdStr(self):
        """Return the command string for the current settings
        """
        cmdStrList = [self.name]
        for stage in self.visibleStageODict.itervalues():
            cmdStrList.append(stage.getCmdStr())
        return " ".join(cmdStrList)        

    @property
    def isCurrent(self):
        """Does the state of the control widgets match the state of the sop command?
        """
        for stage in self.visibleStageODict.itervalues():
            if not stage.isCurrent:
#                print "%s.isCurrent False because %s.isCurrent False" % (self, stage)
                return False
#        print "%s.isCurrent True" % (self,)
        return True

    @property
    def isDefault(self):
        """Is the control widget set to its default state?
        """
        for stage in self.visibleStageODict.itervalues():
            if not stage.isDefault:
#                print "%s.isDefault False because %s.isDefault False" % (self, stage)
                return False
#        print "%s.isDefault True" % (self,)
        return True

    def restoreDefault(self, dumWdg=None):
        """Restore default stages and parameters
        """
        for stage in self.stageDict.itervalues():
            stage.restoreDefault()

    def restoreCurrent(self, dumWdg=None):
        """Restore current parameters
        
        WARNING: it may be better to restore defaults for hidden stages,
        or restore defaults for all, then restore current afterwards.
        On the other hand, maybe that's what restoreCurrent should do anyway.
        """
        for stage in self.stageDict.itervalues():
            stage.restoreCurrent()

    def _commandStagesCallback(self, keyVar):
        """<command>Stages keyword callback
        
        If the list of visible stages changes then regrid all stages and parameters,
        reset all stages and their parameters to default values
        """
#        print "_commandStagesCallback(keyVar=%s)" % (keyVar,)
        newVisibleStageNameList = keyVar[:]
        if not newVisibleStageNameList or None in newVisibleStageNameList:
            return
        if list(self.visibleStageODict.keys()) == newVisibleStageNameList:
            return

        newVisibleStageNameSet = set(newVisibleStageNameList)
        unknownNameSet = newVisibleStageNameSet - set(self.stageDict.keys())
        if unknownNameSet:
            unknownNameList = [str(unk) for unk in unknownNameSet]
            raise RuntimeError("%s contains unknown stages %s" % (keyVar, unknownNameList))

        # withdraw all stages and their parameters
        # and set all stages and parameters to default values
        for stage in self.stageDict.itervalues():
            stage.grid_forget()
            for param in stage.paramList:
                for wdg in param.wdgSet:
                    wdg.grid_forget()
            stage.removeCallback(self.enableWdg, doRaise=False)
            stage.restoreDefault()
        
        # grid visible stages (unless there is only one) and update visibleStageODict
        self.visibleStageODict.clear()
        stageRow = 0
        paramRow = 0
        for stageName in newVisibleStageNameList:
            stage = self.stageDict[stageName]
            if len(newVisibleStageNameList) != 1:
                stage.grid(row=stageRow, column=0, sticky="w")
            stageRow += 1
            
            paramCol = 0
            for param in stage.paramList:
                if param.startNewColumn:
                    paramCol += 4
                    paramRow = 0
                if param.skipRows:
                    paramRow += param.skipRows
                for ind, wdg in enumerate(param.wdgSet):
                    wdg.grid(row = paramRow, column = paramCol + ind, sticky="w")
                paramRow += 1
            self.visibleStageODict[stageName] = stage
            stage.addCallback(self.enableWdg)

    def _commandStateCallback(self, keyVar):
        """<command>State keyword callback

        as of 2010-05-18:
        Key("<command>State",
           String("commandName", help="the name of the sop command"),
           Enum('idle','running','done','failed',
                help="state of the entire command"),
           Enum('idle','off','pending','running','done','failed', 'aborted'
                help="state of all the individual stages of this command...")*(1,6)),
        """
#        print "_commandStateCallback(keyVar=%s)" % (keyVar,)
        
        # set state of the command
        self.setState(
            state=keyVar[0],
            isCurrent = keyVar.isCurrent,
        )
        
        # set state of the command's stages
        stageStateList = keyVar[1:]
        if len(self.visibleStageODict) != len(stageStateList):
            # invalid state data; this can happen for two reasons:
            # - have not yet connected; keyVar values are [None, None]; accept this silently
            # - invalid data; raise an exception
            # in either case null all stage stages since we don't know what they are
            for stage in self.stageDict.itervalues():
                stage.setState(
                    state = None,
                    isCurrent = False,
                )
  
            if None in stageStateList:
                return
            else:
                # log an error message to the status panel? but for now...
                raise RuntimeError("Wrong number of stage states for %s; got %d; expected %d" % 
                    (keyVar.name, len(self.visibleStageODict), len(stageStateList)))

        for stage, stageState in itertools.izip(self.visibleStageODict.itervalues(), stageStateList):
            stage.setState(
                state = stageState,
                isCurrent = keyVar.isCurrent,
            )


class StageWdg(ItemStateWdgSet, Tkinter.Frame):
    """An object representing a SOP command stage
    """
    def __init__(self, master, paramMaster, stageDescr, callFunc=None, helpURL=None):
        """Constructor
        
        Inputs: same as ItemStateWdgSet plus:
        - master: master widget for the stage widget
        - paramMaster: master widget for parameter widgets
        - stageDescr: a StageDescr object describing the stage and its parameters
        """
        Tkinter.Frame.__init__(self, master)
        ItemStateWdgSet.__init__(self,
            master = self,
            name = stageDescr.baseName,
            dispName = stageDescr.dispName,
            callFunc = callFunc,
            helpURL = helpURL,
        )
        self.defEnabled = bool(stageDescr.defEnabled)

        self.paramList = []
        for paramDescr in stageDescr.descrList:
            self.paramList.append(NumericParameterWdgSet(
                master = paramMaster,
                paramDescr = paramDescr,
                callFunc = callFunc,
            ))

        self.controlWdg = RO.Wdg.Checkbutton(
            master = self,
            callFunc = self._controlWdgCallback,
            text = self.dispName,
            autoIsCurrent = True,
            defValue = self.defEnabled,
            helpText = "Enable/disable %s stage" % (self.name,),
            helpURL = self.helpURL,
        )
        self.controlWdg.addCallback(callFunc)
        print "%s controlWdg default=%r" % (self, self.controlWdg.getDefBool())

        self.stateWdg.grid(row=0, column=0, sticky="w")
        self.controlWdg.grid(row=0, column=1, sticky="w")

    def _controlWdgCallback(self, controlWdg=None):
        """Control widget callback
        """
        doEnable = self.controlWdg.getBool()
        for param in self.paramList:
            param.enableWdg(doEnable)
        self.enableWdg()

    def getCmdStr(self):
        """Return the command string for the current settings
        """
        if not self.controlWdg.getBool():
            return "no" + self.name

        cmdStrList = []
        for param in self.paramList:
            cmdStrList.append(param.getCmdStr())
        return " ".join(cmdStrList)

    @property
    def isCurrent(self):
        """Are the stage enabled checkbox and parameters the same as the current or most recent sop command?
        """
        if not self.controlWdg.getIsCurrent():
#            print "%s.isCurrent False because controlWdg.getIsCurrent False" % (self,)
            return False
        for param in self.paramList:
#            print "Test %s.isCurrent" % (param,)
            if not param.isCurrent:
#                print "%s.isCurrent False because %s.isCurrent False" % (self, param)
                return False
#        print "%s.isCurrent True" % (self,)
        return True

    @property
    def isDefault(self):
        """Are the stage enabled checkbox and parameters set to their default state?
        """
        if self.controlWdg.getBool() != self.defEnabled:
#            print "%s.isDefault False because controlWdg.getBool() != self.defEnabled" % (self,)
            return False
        for param in self.paramList:
            if not param.isDefault:
#                print "%s.isDefault False because %s.isDefault False" % (self, param)
                return False
#        print "%s.isDefault True" % (self,)
        return True

    def setState(self, state, isCurrent=True):
        ItemStateWdgSet.setState(self, state, isCurrent=isCurrent)
        
        if state != None:
            isEnabledInSOP = self.state not in self.DisabledStates
            self.controlWdg.setDefault(isEnabledInSOP)
#            print "%s setState set controlWdg default=%r" % (self, self.controlWdg.getDefBool())

    def restoreDefault(self, dumWdg=None):
        """Restore control widget and parameters to their default state.
        """
        self.controlWdg.set(self.defEnabled)
        for param in self.paramList:
            param.restoreDefault()

    def restoreCurrent(self, dumWdg=None):        
        """Restore control widget and parameters to match the running or most recently run command
        """
        # the mechanism for tracking the current value uses the widget's default
        self.controlWdg.restoreDefault()
        for param in self.paramList:
            param.restoreDefault()


class NumericParameterWdgSet(ItemStateWdgSet):
    """An object representing a numeric parameter for a SOP command stage

    A string parameter would be very similar, but with a different isDefault method.
    """
    def __init__(self, master, paramDescr, callFunc=None, helpURL=None):
        """Constructor
        
        Inputs: same as ItemStateWdgSet plus:
        - master: master widget for the stage widget
        - paramMaster: master widget for parameter widgets
        - paramDescr: a ParamDescr object describing the parameter
        """
        ItemStateWdgSet.__init__(self,
            master = master,
            name = paramDescr.baseName,
            dispName = paramDescr.dispName,
            callFunc = callFunc,
            helpURL = helpURL,
        )
        self.defValue = paramDescr.defValue
        self.skipRows = paramDescr.skipRows
        self.startNewColumn = paramDescr.startNewColumn
        self.wdgSet = []
        
        sopModel = TUI.Models.getModel("sop")
        keyVarName = paramDescr.fullName.replace(".", "_")
        print "REGISTER PARAMETER %s with KEYWORD VARIABLE" % (paramDescr.fullName)
        # keyVar = getattr(sopModel, paramDescr.fullName).addCallback(self._keyVarCallback)

#         BaseDescr.__init__(self, baseName, dispName)
#         self.entryWdgClass = entryWdgClass
#         self.entryKeyArgs = entryKeyArgs

        self.controlWdg = paramDescr.entryWdgClass(
            master = master,
            callFunc = callFunc,
            autoIsCurrent = True,
            defValue = self.defValue,
            helpText = "Desired value for %s" % (self.dispName,),
            helpURL = self.helpURL,
        **paramDescr.entryKeyArgs)

        self.wdgSet = [
            self.stateWdg,
        
            RO.Wdg.StrLabel(
                master = master,
                text = paramDescr.dispName,
                helpURL = self.helpURL,
            ),
            
            self.controlWdg,
        ]

        unitsVar = paramDescr.entryKeyArgs.get("unitsVar")
        if unitsVar or paramDescr.units:
            if unitsVar:
                unitsKArgs = dict(textvariable=unitsVar)
            else:
                unitsKArgs = dict(text=paramDescr.units)
            self.wdgSet.append(RO.Wdg.StrLabel(
                master = master,
                helpURL = self.helpURL,
            **unitsKArgs))

    def getCmdStr(self):
        """Return a portion of a command string for this parameter
        """
        strVal = self.controlWdg.getString()
        if not strVal:
            return ""
        return "%s=%s" % (self.name, strVal)

    def _keyVarCallback(self, keyVar):
        """Parameter information keyword variable callback
        """
        print "keyVarCallback: WRITE THIS CODE"

    @property
    def isCurrent(self):
        """Does value of parameter match most current command?
        """
#        print "%s.isCurrent = %r" % (self, self.controlWdg.isDefault())
        return self.controlWdg.isDefault()

    @property
    def isDefault(self):
        """Does value of parameter match most current command?
        """
        if self.defValue == None:
#            print "%s.isDefault False because self.defValue = None" % (self,)
            return False
#        print "%s.isDefault = %s" % (self, abs(self.controlWdg.getNum() - self.defValue) < 1.0e-5)
        return abs(self.controlWdg.getNum() - self.defValue) < 1.0e-5

    def restoreCurrent(self, dumWdg=None):
        """Restore parameter to current state.
        """
        # the mechanism for tracking the current value uses the widget's default
        self.controlWdg.restoreDefault()

    def restoreDefault(self, dumWdg=None):
        """Restore paraemter to default state.
        """
        self.controlWdg.set(self.defValue)


class LoadCartridgeCommandWdg(ItemStateWdgSet, Tkinter.Frame):
    """Guider load cartridge command widget

TO DO:
- What is the command syntax? "loadcartridge"? "load cartridge"? cartridge->cart?
- Can you abort a "load cartridge" command? If so, how?
- Show status a different way:
  - Show name of loaded cartridge of something similar -- science program?
  - There is no guider output I know of that would allow showing all users the state
    of one user's "loadcartridge" command while it runs. As a consequence, I probably
    should NOT try to use the state field to the left of the control
    because it might be confusing. But try it anyway.
    """
    def __init__(self,
        master,
        statusBar,
        callFunc = None,
        helpURL = None,
    ):
        """Create a LoadCartridgeCommandWdg
        
        Inputs: same as ItemStateWdgSet plus:
        - statusBar: status bar widget
        """
        Tkinter.Frame.__init__(self, master)
        ItemStateWdgSet.__init__(self,
            master = self,
            name = "load cartridge",
            dispName = "Load Cartridge",
            callFunc = callFunc,
            helpURL = helpURL,
        )
        self.statusBar = statusBar
        self.actor = "guider"
        self.currCmdInfo = CmdInfo()
        
        self.stateWdg.grid(row=0, column=0, sticky="w")
        self.commandFrame = Tkinter.Frame(self)
        self.commandFrame.grid(row=0, column=1, columnspan=2, sticky="w")
        self._makeCmdWdg()

    def _makeCmdWdg(self):
        self.nameWdg = RO.Wdg.StrLabel(
            master = self.commandFrame,
            text = self.dispName,
            width = CommandNameWidth,
            anchor = "w",
            helpText = "%s command" % (self.name,),
            helpURL = self.helpURL,
        )
        self.nameWdg.pack(side="left")
        
        self.startBtn = RO.Wdg.Button(
            master = self.commandFrame,
            text = "Start",
            callFunc = self.doStart,
            helpText = "Start %s command" % (self.name,),
            helpURL = self.helpURL,
        )
        self.startBtn.pack(side="left")

        self.abortBtn = RO.Wdg.Button(
            master = self.commandFrame,
            text = "X",
            callFunc = self.doAbort,
            helpText = "Abort %s command" % (self.name,),
            helpURL = self.helpURL,
        )
        self.abortBtn.pack(side="left")

    def doAbort(self, wdg=None):
        """Abort the command
        """
        if not self.currCmdInfo.isDone:
            self.currCmdInfo.abort()

    def doStart(self, wdg=None):
        """Start or modify the command
        """
        self.doCmd(self.getCmdStr(), wdg)

    def doCmd(self, cmdStr, wdg=None, **keyArgs):
        """Run the specified command
        
        Inputs:
        - cmdStr: command string
        - wdg: widget that started the command (to disable it while the command runs)
        **keyArgs: all other keyword arguments are used to construct opscore.actor.keyvar.CmdVar
        """
        cmdVar = opscore.actor.keyvar.CmdVar(
            actor = self.actor,
            cmdStr = self.getCmdStr(),
            callFunc = self.enableWdg,
        **keyArgs)
        self.statusBar.doCmd(cmdVar)
        self.currCmdInfo = CmdInfo(cmdVar, wdg)
        self.enableWdg()

    def enableWdg(self, dumWdg=None):
        """Enable widgets according to current state
        """
        self.startBtn.setEnable(self.isDone)
        
        self.abortBtn.setEnable(self.currCmdInfo.isRunning)

        self.currCmdInfo.disableIfRunning()
        
#         severity = RO.Constants.sevNormal
#         if not self.currCmdInfo.cmdVar:
#             state = "Idle"
#         elif self.currCmdInfo.isRunning:
#             state = "Running"
#         elif self.currCmdInfo.didFail:
#             state = "Failed"
#             severity = RO.Constants.sevError
#         elif self.currCmdInfo.isDone:
#             state = "Done"
#         else:
#             state = "?"
#         self.stateWdg.set(state, severity=severity)

    def getCmdStr(self):
        """Return the command string for the current settings
        """
        return "loadcartridge"