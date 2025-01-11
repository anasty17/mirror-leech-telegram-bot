from ...core.config_manager import Config


class BotCommands:
    StartCommand = f"start{Config.CMD_SUFFIX}"
    MirrorCommand = [f"mirror{Config.CMD_SUFFIX}", f"m{Config.CMD_SUFFIX}"]
    QbMirrorCommand = [f"qbmirror{Config.CMD_SUFFIX}", f"qm{Config.CMD_SUFFIX}"]
    JdMirrorCommand = [f"jdmirror{Config.CMD_SUFFIX}", f"jm{Config.CMD_SUFFIX}"]
    YtdlCommand = [f"ytdl{Config.CMD_SUFFIX}", f"y{Config.CMD_SUFFIX}"]
    NzbMirrorCommand = [f"nzbmirror{Config.CMD_SUFFIX}", f"nm{Config.CMD_SUFFIX}"]
    LeechCommand = [f"leech{Config.CMD_SUFFIX}", f"l{Config.CMD_SUFFIX}"]
    QbLeechCommand = [f"qbleech{Config.CMD_SUFFIX}", f"ql{Config.CMD_SUFFIX}"]
    JdLeechCommand = [f"jdLeech{Config.CMD_SUFFIX}", f"jl{Config.CMD_SUFFIX}"]
    YtdlLeechCommand = [f"ytdlleech{Config.CMD_SUFFIX}", f"yl{Config.CMD_SUFFIX}"]
    NzbLeechCommand = [f"nzbleech{Config.CMD_SUFFIX}", f"nl{Config.CMD_SUFFIX}"]
    CloneCommand = f"clone{Config.CMD_SUFFIX}"
    CountCommand = f"count{Config.CMD_SUFFIX}"
    DeleteCommand = f"del{Config.CMD_SUFFIX}"
    CancelTaskCommand = [f"cancel{Config.CMD_SUFFIX}", f"c{Config.CMD_SUFFIX}"]
    CancelAllCommand = f"cancelall{Config.CMD_SUFFIX}"
    ForceStartCommand = [f"forcestart{Config.CMD_SUFFIX}", f"fs{Config.CMD_SUFFIX}"]
    ListCommand = f"list{Config.CMD_SUFFIX}"
    SearchCommand = f"search{Config.CMD_SUFFIX}"
    StatusCommand = f"status{Config.CMD_SUFFIX}"
    UsersCommand = f"users{Config.CMD_SUFFIX}"
    AuthorizeCommand = f"authorize{Config.CMD_SUFFIX}"
    UnAuthorizeCommand = f"unauthorize{Config.CMD_SUFFIX}"
    AddSudoCommand = f"addsudo{Config.CMD_SUFFIX}"
    RmSudoCommand = f"rmsudo{Config.CMD_SUFFIX}"
    PingCommand = f"ping{Config.CMD_SUFFIX}"
    RestartCommand = f"restart{Config.CMD_SUFFIX}"
    RestartSessionsCommand = f"restartses{Config.CMD_SUFFIX}"
    StatsCommand = f"stats{Config.CMD_SUFFIX}"
    HelpCommand = f"help{Config.CMD_SUFFIX}"
    LogCommand = f"log{Config.CMD_SUFFIX}"
    ShellCommand = f"shell{Config.CMD_SUFFIX}"
    AExecCommand = f"aexec{Config.CMD_SUFFIX}"
    ExecCommand = f"exec{Config.CMD_SUFFIX}"
    ClearLocalsCommand = f"clearlocals{Config.CMD_SUFFIX}"
    BotSetCommand = [f"bsetting{Config.CMD_SUFFIX}", f"bs{Config.CMD_SUFFIX}"]
    UserSetCommand = [f"usetting{Config.CMD_SUFFIX}", f"us{Config.CMD_SUFFIX}"]
    SelectCommand = f"sel{Config.CMD_SUFFIX}"
    RssCommand = f"rss{Config.CMD_SUFFIX}"
