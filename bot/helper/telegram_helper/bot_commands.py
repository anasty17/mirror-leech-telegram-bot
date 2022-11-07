from bot import CMD_PERFIX


class _BotCommands:
    def __init__(self):
        self.StartCommand = f'start{CMD_PERFIX}'
        self.MirrorCommand = (f'mirror{CMD_PERFIX}', f'm{CMD_PERFIX}')
        self.UnzipMirrorCommand = (f'unzipmirror{CMD_PERFIX}', f'uzm{CMD_PERFIX}')
        self.ZipMirrorCommand = (f'zipmirror{CMD_PERFIX}', f'zm{CMD_PERFIX}')
        self.QbMirrorCommand = (f'qbmirror{CMD_PERFIX}', f'qm{CMD_PERFIX}')
        self.QbUnzipMirrorCommand = (f'qbunzipmirror{CMD_PERFIX}', f'quzm{CMD_PERFIX}')
        self.QbZipMirrorCommand = (f'qbzipmirror{CMD_PERFIX}', f'qzm{CMD_PERFIX}')
        self.YtdlCommand = (f'ytdl{CMD_PERFIX}', f'y{CMD_PERFIX}')
        self.YtdlZipCommand = (f'ytdlzip{CMD_PERFIX}', f'yz{CMD_PERFIX}')
        self.LeechCommand = (f'leech{CMD_PERFIX}', f'l{CMD_PERFIX}')
        self.UnzipLeechCommand = (f'unzipleech{CMD_PERFIX}', f'uzl{CMD_PERFIX}')
        self.ZipLeechCommand = (f'zipleech{CMD_PERFIX}', f'zl{CMD_PERFIX}')
        self.QbLeechCommand = (f'qbleech{CMD_PERFIX}', f'ql{CMD_PERFIX}')
        self.QbUnzipLeechCommand = (f'qbunzipleech{CMD_PERFIX}', f'quzl{CMD_PERFIX}')
        self.QbZipLeechCommand = (f'qbzipleech{CMD_PERFIX}', f'qzl{CMD_PERFIX}')
        self.YtdlLeechCommand = (f'ytdlleech{CMD_PERFIX}', f'yl{CMD_PERFIX}')
        self.YtdlZipLeechCommand = (f'ytdlzipleech{CMD_PERFIX}', f'yzl{CMD_PERFIX}')
        self.CloneCommand = f'clone{CMD_PERFIX}'
        self.CountCommand = f'count{CMD_PERFIX}'
        self.DeleteCommand = f'del{CMD_PERFIX}'
        self.CancelMirror = f'cancel{CMD_PERFIX}'
        self.CancelAllCommand = f'cancelall{CMD_PERFIX}'
        self.ListCommand = f'list{CMD_PERFIX}'
        self.SearchCommand = f'search{CMD_PERFIX}'
        self.StatusCommand = f'status{CMD_PERFIX}'
        self.UsersCommand = f'users{CMD_PERFIX}'
        self.AuthorizeCommand = f'authorize{CMD_PERFIX}'
        self.UnAuthorizeCommand = f'unauthorize{CMD_PERFIX}'
        self.AddSudoCommand = f'addsudo{CMD_PERFIX}'
        self.RmSudoCommand = f'rmsudo{CMD_PERFIX}'
        self.PingCommand = f'ping{CMD_PERFIX}'
        self.RestartCommand = f'restart{CMD_PERFIX}'
        self.StatsCommand = f'stats{CMD_PERFIX}'
        self.HelpCommand = f'help{CMD_PERFIX}'
        self.LogCommand = f'log{CMD_PERFIX}'
        self.ShellCommand = f'shell{CMD_PERFIX}'
        self.EvalCommand = f'eval{CMD_PERFIX}'
        self.ExecCommand = f'exec{CMD_PERFIX}'
        self.ClearLocalsCommand = f'clearlocals{CMD_PERFIX}'
        self.BotSetCommand = f'bsetting{CMD_PERFIX}'
        self.UserSetCommand = f'usetting{CMD_PERFIX}'
        self.BtSelectCommand = f'btsel{CMD_PERFIX}'
        self.RssListCommand = (f'rsslist{CMD_PERFIX}', f'rl{CMD_PERFIX}')
        self.RssGetCommand = (f'rssget{CMD_PERFIX}', f'rg{CMD_PERFIX}')
        self.RssSubCommand = (f'rsssub{CMD_PERFIX}', f'rs{CMD_PERFIX}')
        self.RssUnSubCommand = (f'rssunsub{CMD_PERFIX}', f'rus{CMD_PERFIX}')
        self.RssSettingsCommand = (f'rssset{CMD_PERFIX}', f'rst{CMD_PERFIX}')

BotCommands = _BotCommands()
