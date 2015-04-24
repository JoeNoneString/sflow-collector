import utils
import sflow
import app_manager


#from oslo.config import cfg
from oslo_config import cfg

opts = [cfg.StrOpt('address', default='0.0.0.0',
                   help='sFlow Collector bind address'),
        cfg.IntOpt('port', default=6343,
                   help='sFlow Collector port'),
        cfg.IntOpt('max_udp_msg_size', default=1472,
                   help='Maximum size of UDP messages')
]
CONF = cfg.CONF
CONF.register_opts(opts, 'plow')


class SFlow(app_manager.RyuApp):
    def __init__(self, *args, **kwargs):
        super(SFlow, self).__init__(*args, **kwargs)
        self._address = cfg.CONF.plow.address
        self._port = cfg.CONF.plow.port
        self._udp_msg_size = cfg.CONF.plow.max_udp_msg_size
        self._udp_sock = None

    def _handle(self, buf, addr):
        packet = sflow.sFlow.parser(buf)

        if not packet:
            return

        print packet.__dict__['samples']

    def _recv_loop(self):
        self.logger.info('Listening on %s:%s for sflow agents' %
                         (self._address, self._port))

        while True:
            buf, addr = self._udp_sock.recvfrom(self._udp_msg_size)
            t = utils.spawn(self._handle, buf, addr)
            self.threads.append(t)

    def start(self):
        self._udp_sock = utils.socket.socket(utils.socket.AF_INET,
                                           utils.socket.SOCK_DGRAM)
        self._udp_sock.bind((self._address, self._port))

        t = utils.spawn(self._recv_loop)
        super(SFlow, self).start()
        return t
