import sys
from types import ModuleType
from unittest.mock import MagicMock

fake_ck = ModuleType('confluent_kafka')
fake_ck.Producer = MagicMock
fake_ck.Consumer = MagicMock
fake_ck.KafkaError = type('KafkaError', (), {'_PARTITION_EOF': -191})

fake_admin = ModuleType('confluent_kafka.admin')
fake_admin.AdminClient = MagicMock
fake_admin.NewTopic = MagicMock

sys.modules.setdefault('confluent_kafka', fake_ck)
sys.modules.setdefault('confluent_kafka.admin', fake_admin)
