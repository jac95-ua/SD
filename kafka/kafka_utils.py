"""Utilidades para manejo de configuración y Kafka."""
import yaml
import json
from typing import Dict, List, Any
from pathlib import Path


def load_config(config_path: str = "kafka_config.yaml") -> Dict[str, Any]:
    """Carga la configuración desde el archivo YAML."""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def get_bootstrap_servers(config: Dict[str, Any]) -> List[str]:
    """Obtiene la lista de bootstrap servers de Kafka."""
    return config['kafka']['bootstrap_servers']


def get_topics(config: Dict[str, Any]) -> Dict[str, str]:
    """Obtiene el mapeo de nombres lógicos a nombres reales de topics."""
    return config['kafka']['topics']


def get_consumer_config(role: str, config: Dict[str, Any], instance_id: str = None) -> Dict[str, Any]:
    """Obtiene la configuración de consumer para un rol específico."""
    role_config = config['roles'][role]
    
    # Determinar el consumer group
    if 'consumer_group_template' in role_config:
        if not instance_id:
            raise ValueError(f"instance_id requerido para rol {role}")
        consumer_group = role_config['consumer_group_template'].format(**{f"{role}_id": instance_id})
    else:
        consumer_group = role_config['consumer_group']
    
    return {
        'bootstrap_servers': get_bootstrap_servers(config),
        'group_id': consumer_group,
        'auto_offset_reset': 'latest',
        'value_deserializer': lambda x: json.loads(x.decode('utf-8')) if x else None
    }


def get_producer_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Obtiene la configuración de producer."""
    return {
        'bootstrap_servers': get_bootstrap_servers(config),
        'value_serializer': lambda x: json.dumps(x, ensure_ascii=False).encode('utf-8')
    }


def get_role_topics(role: str, config: Dict[str, Any], topic_type: str) -> List[str]:
    """Obtiene los topics para un rol específico (consumer o producer)."""
    role_config = config['roles'][role]
    topic_names = role_config[f'{topic_type}_topics']
    topics_map = get_topics(config)
    
    return [topics_map[topic_name] for topic_name in topic_names]


class KafkaMessage:
    """Wrapper para mensajes de Kafka que mantiene compatibilidad con el protocolo original."""
    
    @staticmethod
    def to_kafka_message(tipo: str, source: str, id_: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Convierte un mensaje del protocolo original a formato Kafka."""
        return {
            "tipo": tipo,
            "source": source, 
            "id": id_,
            "payload": payload,
            "timestamp": None  # Se añadirá automáticamente por Kafka
        }
    
    @staticmethod
    def from_kafka_message(kafka_msg) -> Dict[str, Any]:
        """Extrae el mensaje del formato Kafka."""
        return kafka_msg.value


def make_msg(tipo: str, source: str, id_: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Mantiene compatibilidad con el protocolo original."""
    return KafkaMessage.to_kafka_message(tipo, source, id_, payload)