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
        # Load configuration from the YAML file

        self.config = config

        self.logger = logger

        self.extracted_values = {
            "IMSI": None,
            "nodebid": None,
            "rrc_state": None,
            "rsrp": None,
            "sinr": None,
            "rsrq": None,
        }


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
                # Poll for new messages
                message = self.consumer.poll(timeout=self.config['kafka']['poll_timeout_seconds'])

                if message is None:
                    continue

                if message.error():
                    logger.error(f"Error consuming message: {message.error()}")
                    continue

                # Process the consumed message
                self.extract_measurements(message)
            except Exception as e:
                logger.error(f"Exception occurred while consuming message: {str(e)}")

    def extract_measurements(self, message):
        message_content = json.loads(message.value().decode('utf-8'))
         
        # Extract IMSI
        self.extracted_values["IMSI"] = message_content["event"]["commonEventHeader"]["sourceName"].strip("'")

        # Iterate through additionalObjects to find and extract values
        for obj in message_content["event"]["measurementsForVfScalingFields"]["additionalObjects"]:
            object_name = obj["objectName"]
            for instance in obj["objectInstances"]:
                # Extract nodebid common for all measurements, assuming it's the same for all instances
                for key in instance["objectKeys"]:
                    if key["keyName"] == "ricComponentName":
                        # Ensure nodebid is extracted and formatted as '72411_00000002'
                        nodebid = key["keyValue"].strip("'")
                        self.extracted_values["nodebid"] = nodebid
                        break

                if object_name == "e2sm_rc_report_style4_rrc_state":
                    self.extracted_values["rrc_state"] = list(instance["objectInstance"].values())[0]
                elif object_name == "e2sm_rc_report_style4_rsrp":
                    self.extracted_values["rsrp"] = list(instance["objectInstance"].values())[0]
                elif object_name == "e2sm_rc_report_style4_sinr":
                    self.extracted_values["sinr"] = list(instance["objectInstance"].values())[0]
                elif object_name == "e2sm_rc_report_style4_rsrq":
                    self.extracted_values["rsrq"] = list(instance["objectInstance"].values())[0]
        logger.info(f"Extracted measurements: {self.extracted_values}")
        return self.extracted_values

    def run(self):
        self.logger.info('Running the UE consumer application.')
        self.logger.debug('Configuration: %s', self.config)
        self.consume_messages()
        return self.extracted_values