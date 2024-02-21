import json
import logging
from confluent_kafka import Consumer

logger = logging.getLogger(__name__)

class UEConsumer:

    def __init__(self, logger, config):
        """
        Initializes a new instance of the UEConsumer class.

        Args:
            config_file_path (str): The path to the YAML configuration file.
        """
        self.config = config
        self.logger = logger

        # Store UE data keyed by IMSI
        self.ue_data = {}

        # Kafka consumer configuration
        kafka_config = {
            'bootstrap.servers': self.config['kafka']['bootstrap_servers'],
            'group.id': self.config['kafka']['group_id'],
            'auto.offset.reset': self.config['kafka']['auto_offset_reset'],
            'enable.auto.commit': self.config['kafka']['enable_auto_commit'],
            'auto.commit.interval.ms': self.config['kafka']['auto_commit_interval_ms'],
            'client.id': self.config['kafka']['client_id']
        }

        # Create Kafka consumer instance
        self.consumer = Consumer(kafka_config)

        # Subscribe to Kafka topics
        topics = self.config['kafka']['topics']
        self.consumer.subscribe(topics)

    def consume_messages(self):
        """
        Consumes messages from Kafka topics.
        """
        while True:
            try:
                message = self.consumer.poll(timeout=self.config['kafka']['poll_timeout_seconds'])
                if message is None:
                    continue
                if message.error():
                    logger.error(f"Error consuming message: {message.error()}")
                    continue
                self.extract_measurements(message)
            except Exception as e:
                logger.error(f"Exception occurred while consuming message: {str(e)}")

    def extract_measurements(self, message):
        message_content = json.loads(message.value().decode('utf-8'))
        imsi = message_content["event"]["commonEventHeader"]["sourceName"].strip("'")

        # Initialize a dictionary for the current message if IMSI does not exist
        if imsi not in self.ue_data:
            self.ue_data[imsi] = {
                "IMSI": imsi,
                "nodebid": None,
                "rrc_state": None,
                "rsrp": None,
                "sinr": None,
                "rsrq": None,
            }

        # Extract and update values
        for obj in message_content["event"]["measurementsForVfScalingFields"]["additionalObjects"]:
            object_name = obj["objectName"]
            for instance in obj["objectInstances"]:
                for key in instance["objectKeys"]:
                    if key["keyName"] == "ricComponentName":
                        nodebid = key["keyValue"].strip("'")
                        self.ue_data[imsi]["nodebid"] = nodebid
                        break

                if object_name == "e2sm_rc_report_style4_rrc_state":
                    self.ue_data[imsi]["rrc_state"] = list(instance["objectInstance"].values())[0]
                elif object_name == "e2sm_rc_report_style4_rsrp":
                    self.ue_data[imsi]["rsrp"] = list(instance["objectInstance"].values())[0]
                elif object_name == "e2sm_rc_report_style4_sinr":
                    self.ue_data[imsi]["sinr"] = list(instance["objectInstance"].values())[0]
                elif object_name == "e2sm_rc_report_style4_rsrq":
                    self.ue_data[imsi]["rsrq"] = list(instance["objectInstance"].values())[0]

        logger.debug(f"Updated UE data: {self.ue_data[imsi]}")
        logger.debug(json.dumps(self.ue_data))  # Log ue_data as JSON
        return self.ue_data[imsi]

    def run(self):
        self.logger.info('Running the UE consumer application.')
        self.logger.debug('Configuration: %s', self.config)
        self.consume_messages()
        # Since ue_data now stores multiple UEs, you might want to consider how you use this data outside this method

