from bot import CMD_SUFFIX


class _BotCommands:
    def __init__(self):
        self.StartCommand = f'start{CMD_SUFFIX}'
        self.MirrorCommand = [f'mirror{CMD_SUFFIX}', f'm{CMD_SUFFIX}']
        self.UnzipMirrorCommand = [f'unzipmirror{CMD_SUFFIX}', f'uzm{CMD_SUFFIX}']
        self.ZipMirrorCommand = [f'zipmirror{CMD_SUFFIX}', f'zm{CMD_SUFFIX}']
        self.QbMirrorCommand = [f'qbmirror{CMD_SUFFIX}', f'qm{CMD_SUFFIX}']
        self.QbUnzipMirrorCommand = [f'qbunzipmirror{CMD_SUFFIX}', f'quzm{CMD_SUFFIX}']
        self.QbZipMirrorCommand = [f'qbzipmirror{CMD_SUFFIX}', f'qzm{CMD_SUFFIX}']
        self.YtdlCommand = [f'ytdl{CMD_SUFFIX}', f'y{CMD_SUFFIX}']
        self.YtdlZipCommand = [f'ytdlzip{CMD_SUFFIX}', f'yz{CMD_SUFFIX}']
        self.LeechCommand = [f'leech{CMD_SUFFIX}', f'l{CMD_SUFFIX}']
        self.UnzipLeechCommand = [f'unzipleech{CMD_SUFFIX}', f'uzl{CMD_SUFFIX}']
        self.ZipLeechCommand = [f'zipleech{CMD_SUFFIX}', f'zl{CMD_SUFFIX}']
        self.QbLeechCommand = [f'qbleech{CMD_SUFFIX}', f'ql{CMD_SUFFIX}']
        self.QbUnzipLeechCommand = [f'qbunzipleech{CMD_SUFFIX}', f'quzl{CMD_SUFFIX}']
        self.QbZipLeechCommand = [f'qbzipleech{CMD_SUFFIX}', f'qzl{CMD_SUFFIX}']
        self.YtdlLeechCommand = [f'ytdlleech{CMD_SUFFIX}', f'yl{CMD_SUFFIX}']
        self.YtdlZipLeechCommand = [f'ytdlzipleech{CMD_SUFFIX}', f'yzl{CMD_SUFFIX}']
        self.CloneCommand = f'clone{CMD_SUFFIX}'
        self.CountCommand = f'count{CMD_SUFFIX}'
        self.DeleteCommand = f'del{CMD_SUFFIX}'
        self.CancelMirror = f'cancel{CMD_SUFFIX}'
        self.CancelAllCommand = f'cancelall{CMD_SUFFIX}'
        self.ListCommand = f'list{CMD_SUFFIX}'
        self.SearchCommand = f'search{CMD_SUFFIX}'
        self.StatusCommand = f'status{CMD_SUFFIX}'
        self.UsersCommand = f'users{CMD_SUFFIX}'
        self.AuthorizeCommand = f'authorize{CMD_SUFFIX}'
        self.UnAuthorizeCommand = f'unauthorize{CMD_SUFFIX}'
        self.AddSudoCommand = f'addsudo{CMD_SUFFIX}'
        self.RmSudoCommand = f'rmsudo{CMD_SUFFIX}'
        self.PingCommand = f'ping{CMD_SUFFIX}'
        self.RestartCommand = f'restart{CMD_SUFFIX}'
        self.StatsCommand = f'stats{CMD_SUFFIX}'
        self.HelpCommand = f'help{CMD_SUFFIX}'
        self.LogCommand = f'log{CMD_SUFFIX}'
        self.ShellCommand = f'shell{CMD_SUFFIX}'
        self.EvalCommand = f'eval{CMD_SUFFIX}'
        self.ExecCommand = f'exec{CMD_SUFFIX}'
        self.ClearLocalsCommand = f'clearlocals{CMD_SUFFIX}'
        self.BotSetCommand = f'bsetting{CMD_SUFFIX}'
        self.UserSetCommand = f'usetting{CMD_SUFFIX}'
        self.BtSelectCommand = f'btsel{CMD_SUFFIX}'
        self.RssCommand = f'rss{CMD_SUFFIX}'

BotCommands = _BotCommands()