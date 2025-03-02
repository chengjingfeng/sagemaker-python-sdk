# Copyright 2018-2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You
# may not use this file except in compliance with the License. A copy of
# the License is located at
#
#     http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
# ANY KIND, either express or implied. See the License for the specific
# language governing permissions and limitations under the License.
from __future__ import absolute_import

import enum
import logging
import re

from sagemaker.estimator import Framework
import sagemaker.fw_utils as fw_utils
from sagemaker.model import FrameworkModel, SAGEMAKER_OUTPUT_LOCATION
from sagemaker.mxnet.model import MXNetModel
from sagemaker.vpc_utils import VPC_CONFIG_DEFAULT

logger = logging.getLogger("sagemaker")

SAGEMAKER_ESTIMATOR = "sagemaker_estimator"
SAGEMAKER_ESTIMATOR_VALUE = "RLEstimator"
PYTHON_VERSION = "py3"
TOOLKIT_FRAMEWORK_VERSION_MAP = {
    "coach": {
        "0.10.1": {"tensorflow": "1.11"},
        "0.10": {"tensorflow": "1.11"},
        "0.11.0": {"tensorflow": "1.11", "mxnet": "1.3"},
        "0.11.1": {"tensorflow": "1.12"},
        "0.11": {"tensorflow": "1.12", "mxnet": "1.3"},
    },
    "ray": {
        "0.5.3": {"tensorflow": "1.11"},
        "0.5": {"tensorflow": "1.11"},
        "0.6.5": {"tensorflow": "1.12"},
        "0.6": {"tensorflow": "1.12"},
    },
}


class RLToolkit(enum.Enum):
    COACH = "coach"
    RAY = "ray"


class RLFramework(enum.Enum):
    TENSORFLOW = "tensorflow"
    MXNET = "mxnet"


class RLEstimator(Framework):
    """Handle end-to-end training and deployment of custom RLEstimator code."""

    COACH_LATEST_VERSION_TF = "0.11.1"
    COACH_LATEST_VERSION_MXNET = "0.11.0"
    RAY_LATEST_VERSION = "0.6.5"

    def __init__(
        self,
        entry_point,
        toolkit=None,
        toolkit_version=None,
        framework=None,
        source_dir=None,
        hyperparameters=None,
        image_name=None,
        metric_definitions=None,
        **kwargs
    ):
        """This Estimator executes an RLEstimator script in a managed
        Reinforcement Learning (RL) execution environment within a SageMaker Training Job.
        The managed RL environment is an Amazon-built Docker container that executes
        functions defined in the supplied ``entry_point`` Python script.

        Training is started by calling :meth:`~sagemaker.amazon.estimator.Framework.fit`
        on this Estimator. After training is complete, calling
        :meth:`~sagemaker.amazon.estimator.Framework.deploy` creates a
        hosted SageMaker endpoint and based on the specified framework returns
        an :class:`~sagemaker.amazon.mxnet.model.MXNetPredictor` or
        :class:`~sagemaker.amazon.tensorflow.serving.Predictor` instance
        that can be used to perform inference against the hosted model.

        Technical documentation on preparing RLEstimator scripts for SageMaker training
        and using the RLEstimator is available on the project homepage:
        https://github.com/aws/sagemaker-python-sdk

        Args:
            entry_point (str): Path (absolute or relative) to the Python source file
                which should be executed as the entry point to training.
                This should be compatible with Python 3.5 for MXNet or Python 3.6 for TensorFlow.
            toolkit (sagemaker.rl.RLToolkit): RL toolkit you want to use
                for executing your model training code.
            toolkit_version (str): RL toolkit version you want to be use
                for executing your model training code.
            framework (sagemaker.rl.RLFramework): Framework (MXNet or TensorFlow)
                you want to be used as a toolkit backed for reinforcement learning training.
            source_dir (str): Path (absolute or relative) to a directory with any other training
                source code dependencies aside from the entry point file (default: None).
                Structure within this directory is preserved when training on Amazon SageMaker.
            hyperparameters (dict): Hyperparameters that will be used for training (default: None).
                The hyperparameters are made accessible as a dict[str, str]
                to the training code on SageMaker. For convenience, this accepts other types
                for keys and values.
            image_name (str): An ECR url. If specified, the estimator will use this image
                for training and hosting, instead of selecting the appropriate SageMaker
                official image based on framework_version and py_version.
                Example: 123.dkr.ecr.us-west-2.amazonaws.com/my-custom-image:1.0
            metric_definitions (list[dict]): A list of dictionaries that defines the metric(s)
                used to evaluate the training jobs. Each dictionary contains two keys:
                'Name' for the name of the metric, and 'Regex' for the regular expression used to
                extract the metric from the logs. This should be defined only for jobs
                that don't use an Amazon algorithm.
            **kwargs: Additional kwargs passed to the :class:`~sagemaker.estimator.Framework`
                constructor.
        """
        self._validate_images_args(toolkit, toolkit_version, framework, image_name)

        if not image_name:
            self._validate_toolkit_support(toolkit.value, toolkit_version, framework.value)
            self.toolkit = toolkit.value
            self.toolkit_version = toolkit_version
            self.framework = framework.value
            self.framework_version = TOOLKIT_FRAMEWORK_VERSION_MAP[self.toolkit][
                self.toolkit_version
            ][self.framework]

            # set default metric_definitions based on the toolkit
            if not metric_definitions:
                metric_definitions = self.default_metric_definitions(toolkit)

        super(RLEstimator, self).__init__(
            entry_point,
            source_dir,
            hyperparameters,
            image_name=image_name,
            metric_definitions=metric_definitions,
            **kwargs
        )

    def create_model(
        self,
        role=None,
        vpc_config_override=VPC_CONFIG_DEFAULT,
        entry_point=None,
        source_dir=None,
        dependencies=None,
    ):
        """Create a SageMaker ``RLEstimatorModel`` object that can be deployed to an Endpoint.

        Args:
            role (str): The ``ExecutionRoleArn`` IAM Role ARN for the ``Model``, which is also used
                during transform jobs. If not specified, the role from the Estimator will be used.
            vpc_config_override (dict[str, list[str]]): Optional override for VpcConfig
                set on the model. Default: use subnets and security groups from this Estimator.

                * 'Subnets' (list[str]): List of subnet ids.
                * 'SecurityGroupIds' (list[str]): List of security group ids.

            entry_point (str): Path (absolute or relative) to the Python source file
                which should be executed as the entry point for MXNet hosting.
                This should be compatible with Python 3.5 (default: self.entry_point)
            source_dir (str): Path (absolute or relative) to a directory with any other training
                source code dependencies aside from tne entry point file (default: self.source_dir).
                Structure within this directory are preserved when hosting on Amazon SageMaker.
            dependencies (list[str]): A list of paths to directories (absolute or relative) with
                any additional libraries that will be exported to the container
                (default: self.dependencies). The library folders will be copied to SageMaker
                in the same folder where the entry_point is copied. If the ```source_dir``` points
                to S3, code will be uploaded and the S3 location will be used instead.

        Returns:
            sagemaker.model.FrameworkModel: Depending on input parameters returns
                one of the following:

                * sagemaker.model.FrameworkModel - in case image_name was specified
                    on the estimator;
                * sagemaker.mxnet.MXNetModel - if image_name wasn't specified and
                    MXNet was used as RL backend;
                * sagemaker.tensorflow.serving.Model - if image_name wasn't specified and
                    TensorFlow was used as RL backend.

        """
        base_args = dict(
            model_data=self.model_data,
            role=role or self.role,
            image=self.image_name,
            name=self._current_job_name,
            container_log_level=self.container_log_level,
            sagemaker_session=self.sagemaker_session,
            vpc_config=self.get_vpc_config(vpc_config_override),
        )

        if not entry_point and (source_dir or dependencies):
            raise AttributeError("Please provide an `entry_point`.")

        entry_point = entry_point or self.entry_point
        source_dir = source_dir or self._model_source_dir()
        dependencies = dependencies or self.dependencies

        extended_args = dict(
            entry_point=entry_point,
            source_dir=source_dir,
            code_location=self.code_location,
            dependencies=dependencies,
            enable_cloudwatch_metrics=self.enable_cloudwatch_metrics,
        )
        extended_args.update(base_args)

        if self.image_name:
            return FrameworkModel(**extended_args)

        if self.toolkit == RLToolkit.RAY.value:
            raise NotImplementedError(
                "Automatic deployment of Ray models is not currently available."
                " Train policy parameters are available in model checkpoints"
                " in the TrainingJob output."
            )

        if self.framework == RLFramework.TENSORFLOW.value:
            from sagemaker.tensorflow.serving import Model as tfsModel

            return tfsModel(framework_version=self.framework_version, **base_args)
        if self.framework == RLFramework.MXNET.value:
            return MXNetModel(
                framework_version=self.framework_version, py_version=PYTHON_VERSION, **extended_args
            )

    def train_image(self):
        """Return the Docker image to use for training.

        The :meth:`~sagemaker.estimator.EstimatorBase.fit` method, which does the model training,
        calls this method to find the image to use for model training.

        Returns:
            str: The URI of the Docker image.
        """
        if self.image_name:
            return self.image_name
        return fw_utils.create_image_uri(
            self.sagemaker_session.boto_region_name,
            self._image_framework(),
            self.train_instance_type,
            self._image_version(),
            py_version=PYTHON_VERSION,
        )

    @classmethod
    def _prepare_init_params_from_job_description(cls, job_details, model_channel_name=None):
        """Convert the job description to init params that can be handled by the class constructor

        Args:
            job_details: the returned job details from a describe_training_job API call.
            model_channel_name (str): Name of the channel where pre-trained model data will be
                downloaded.

        Returns:
             dictionary: The transformed init_params
        """
        init_params = super(RLEstimator, cls)._prepare_init_params_from_job_description(
            job_details, model_channel_name
        )

        image_name = init_params.pop("image")
        framework, _, tag, _ = fw_utils.framework_name_from_image(image_name)

        if not framework:
            # If we were unable to parse the framework name from the image it is not one of our
            # officially supported images, in this case just add the image to the init params.
            init_params["image_name"] = image_name
            return init_params

        toolkit, toolkit_version = cls._toolkit_and_version_from_tag(tag)

        if not cls._is_combination_supported(toolkit, toolkit_version, framework):
            training_job_name = init_params["base_job_name"]
            raise ValueError(
                "Training job: {} didn't use image for requested framework".format(
                    training_job_name
                )
            )

        init_params["toolkit"] = RLToolkit(toolkit)
        init_params["toolkit_version"] = toolkit_version
        init_params["framework"] = RLFramework(framework)

        return init_params

    def hyperparameters(self):
        """Return hyperparameters used by your custom TensorFlow code during model training."""
        hyperparameters = super(RLEstimator, self).hyperparameters()

        additional_hyperparameters = {
            SAGEMAKER_OUTPUT_LOCATION: self.output_path,
            # TODO: can be applied to all other estimators
            SAGEMAKER_ESTIMATOR: SAGEMAKER_ESTIMATOR_VALUE,
        }

        hyperparameters.update(Framework._json_encode_hyperparameters(additional_hyperparameters))
        return hyperparameters

    @classmethod
    def _toolkit_and_version_from_tag(cls, image_tag):
        tag_pattern = re.compile(
            "^([A-Z]*|[a-z]*)(\d.*)-(cpu|gpu)-(py2|py3)$"  # noqa: W605,E501 pylint: disable=anomalous-backslash-in-string
        )
        tag_match = tag_pattern.match(image_tag)
        if tag_match is not None:
            return tag_match.group(1), tag_match.group(2)
        return None, None

    @classmethod
    def _validate_framework_format(cls, framework):
        if framework and framework not in RLFramework:
            raise ValueError(
                "Invalid type: {}, valid RL frameworks types are: [{}]".format(
                    framework, [t for t in RLFramework]
                )
            )

    @classmethod
    def _validate_toolkit_format(cls, toolkit):
        if toolkit and toolkit not in RLToolkit:
            raise ValueError(
                "Invalid type: {}, valid RL toolkits types are: [{}]".format(
                    toolkit, [t for t in RLToolkit]
                )
            )

    @classmethod
    def _validate_images_args(cls, toolkit, toolkit_version, framework, image_name):
        cls._validate_toolkit_format(toolkit)
        cls._validate_framework_format(framework)

        if not image_name:
            not_found_args = []
            if not toolkit:
                not_found_args.append("toolkit")
            if not toolkit_version:
                not_found_args.append("toolkit_version")
            if not framework:
                not_found_args.append("framework")
            if not_found_args:
                raise AttributeError(
                    "Please provide `{}` or `image_name` parameter.".format(
                        "`, `".join(not_found_args)
                    )
                )
        else:
            found_args = []
            if toolkit:
                found_args.append("toolkit")
            if toolkit_version:
                found_args.append("toolkit_version")
            if framework:
                found_args.append("framework")
            if found_args:
                logger.warning(
                    "Parameter `image_name` is specified, "
                    "`%s` are going to be ignored when choosing the image.",
                    "`, `".join(found_args),
                )

    @classmethod
    def _is_combination_supported(cls, toolkit, toolkit_version, framework):
        supported_versions = TOOLKIT_FRAMEWORK_VERSION_MAP.get(toolkit, None)
        if supported_versions:
            supported_frameworks = supported_versions.get(toolkit_version, None)
            if supported_frameworks and supported_frameworks.get(framework, None):
                return True
        return False

    @classmethod
    def _validate_toolkit_support(cls, toolkit, toolkit_version, framework):
        if not cls._is_combination_supported(toolkit, toolkit_version, framework):
            raise AttributeError(
                "Provided `{}-{}` and `{}` combination is not supported.".format(
                    toolkit, toolkit_version, framework
                )
            )

    def _image_version(self):
        return "{}{}".format(self.toolkit, self.toolkit_version)

    def _image_framework(self):
        return "rl-{}".format(self.framework)

    @classmethod
    def default_metric_definitions(cls, toolkit):
        """Provides default metric definitions based on provided toolkit.

        Args:
            toolkit(sagemaker.rl.RLToolkit): RL Toolkit to be used for training.

        Returns:
            list: metric definitions
        """
        if toolkit is RLToolkit.COACH:
            return [
                {"Name": "reward-training", "Regex": "^Training>.*Total reward=(.*?),"},
                {"Name": "reward-testing", "Regex": "^Testing>.*Total reward=(.*?),"},
            ]
        if toolkit is RLToolkit.RAY:
            float_regex = "[-+]?[0-9]*[.]?[0-9]+([eE][-+]?[0-9]+)?"  # noqa: W605, E501

            return [
                {"Name": "episode_reward_mean", "Regex": "episode_reward_mean: (%s)" % float_regex},
                {"Name": "episode_reward_max", "Regex": "episode_reward_max: (%s)" % float_regex},
            ]
