from ...core.config_manager import Config

i = Config.CMD_SUFFIX

class BotCommands:
    StartCommand = f"start{i}"
    MirrorCommand = [f"mirror{i}", f"m{i}"]
    QbMirrorCommand = [f"qbmirror{i}", f"qm{i}"]
    JdMirrorCommand = [f"jdmirror{i}", f"jm{i}"]
    YtdlCommand = [f"ytdl{i}", f"y{i}"]
    NzbMirrorCommand = [f"nzbmirror{i}", f"nm{i}"]
    LeechCommand = [f"leech{i}", f"l{i}"]
    QbLeechCommand = [f"qbleech{i}", f"ql{i}"]
    JdLeechCommand = [f"jdleech{i}", f"jl{i}"]
    YtdlLeechCommand = [f"ytdlleech{i}", f"yl{i}"]
    NzbLeechCommand = [f"nzbleech{i}", f"nl{i}"]
    CloneCommand = f"clone{i}"
    CountCommand = f"count{i}"
    DeleteCommand = f"del{i}"
    CancelTaskCommand = [f"cancel{i}", f"c{i}"]
    CancelAllCommand = f"cancelall{i}"
    ForceStartCommand = [f"forcestart{i}", f"fs{i}"]
    ListCommand = f"list{i}"
    SearchCommand = f"search{i}"
    StatusCommand = f"status{i}"
    UsersCommand = f"users{i}"
    AuthorizeCommand = f"auth{i}"
    UnAuthorizeCommand = f"unauth{i}"
    AddSudoCommand = f"addsudo{i}"
    RmSudoCommand = f"rmsudo{i}"
    PingCommand = f"ping{i}"
    RestartCommand = f"restart{i}"
    RestartSessionsCommand = f"restartses{i}"
    StatsCommand = f"stats{i}"
    HelpCommand = f"help{i}"
    LogCommand = f"log{i}"
    ShellCommand = f"shell{i}"
    AExecCommand = f"aexec{i}"
    ExecCommand = f"exec{i}"
    ClearLocalsCommand = f"clearlocals{i}"
    BotSetCommand = [f"bsetting{i}", f"bs{i}"]
    UserSetCommand = [f"usetting{i}", f"us{i}"]
    SelectCommand = f"sel{i}"
    RssCommand = f"rss{i}"
    NzbSearchCommand = f"nzbsearch{i}"
