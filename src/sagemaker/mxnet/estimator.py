# Copyright 2017-2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
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

import logging

from sagemaker.estimator import Framework
from sagemaker.fw_utils import (
    framework_name_from_image,
    framework_version_from_tag,
    empty_framework_version_warning,
    python_deprecation_warning,
)
from sagemaker.mxnet.defaults import MXNET_VERSION
from sagemaker.mxnet.model import MXNetModel
from sagemaker.vpc_utils import VPC_CONFIG_DEFAULT

logger = logging.getLogger("sagemaker")


class MXNet(Framework):
    """Handle end-to-end training and deployment of custom MXNet code."""

    __framework_name__ = "mxnet"
    _LOWEST_SCRIPT_MODE_VERSION = ["1", "3"]

    LATEST_VERSION = "1.4"
    """The latest version of MXNet included in the SageMaker pre-built Docker images."""

    def __init__(
        self,
        entry_point,
        source_dir=None,
        hyperparameters=None,
        py_version="py2",
        framework_version=None,
        image_name=None,
        distributions=None,
        **kwargs
    ):
        """
        This ``Estimator`` executes an MXNet script in a managed MXNet execution environment, within a SageMaker
        Training Job. The managed MXNet environment is an Amazon-built Docker container that executes functions
        defined in the supplied ``entry_point`` Python script.

        Training is started by calling :meth:`~sagemaker.amazon.estimator.Framework.fit` on this Estimator.
        After training is complete, calling :meth:`~sagemaker.amazon.estimator.Framework.deploy` creates a
        hosted SageMaker endpoint and returns an :class:`~sagemaker.amazon.mxnet.model.MXNetPredictor` instance
        that can be used to perform inference against the hosted model.

        Technical documentation on preparing MXNet scripts for SageMaker training and using the MXNet Estimator is
        available on the project home-page: https://github.com/aws/sagemaker-python-sdk

        Args:
            entry_point (str): Path (absolute or relative) to the Python source file which should be executed
                as the entry point to training. This should be compatible with either Python 2.7 or Python 3.5.
            source_dir (str): Path (absolute or relative) to a directory with any other training
                source code dependencies aside from tne entry point file (default: None). Structure within this
                directory are preserved when training on Amazon SageMaker.
            hyperparameters (dict): Hyperparameters that will be used for training (default: None).
                The hyperparameters are made accessible as a dict[str, str] to the training code on SageMaker.
                For convenience, this accepts other types for keys and values, but ``str()`` will be called
                to convert them before training.
            py_version (str): Python version you want to use for executing your model training code (default: 'py2').
                One of 'py2' or 'py3'.
            framework_version (str): MXNet version you want to use for executing your model training code.
                List of supported versions https://github.com/aws/sagemaker-python-sdk#mxnet-sagemaker-estimators.
                If not specified, this will default to 1.2.1.
            image_name (str): If specified, the estimator will use this image for training and hosting, instead of
                selecting the appropriate SageMaker official image based on framework_version and py_version. It can
                be an ECR url or dockerhub image and tag.

                Examples:
                    123.dkr.ecr.us-west-2.amazonaws.com/my-custom-image:1.0
                    custom-image:latest.
             distributions (dict): A dictionary with information on how to run distributed training
                (default: None).
            **kwargs: Additional kwargs passed to the :class:`~sagemaker.estimator.Framework` constructor.
        """
        if framework_version is None:
            logger.warning(empty_framework_version_warning(MXNET_VERSION, self.LATEST_VERSION))
        self.framework_version = framework_version or MXNET_VERSION

        super(MXNet, self).__init__(
            entry_point, source_dir, hyperparameters, image_name=image_name, **kwargs
        )

        if py_version == "py2":
            logger.warning(python_deprecation_warning(self.__framework_name__))

        self.py_version = py_version
        self._configure_distribution(distributions)

    def _configure_distribution(self, distributions):
        if distributions is None:
            return

        if self.framework_version.split(".") < self._LOWEST_SCRIPT_MODE_VERSION:
            raise ValueError(
                "The distributions option is valid for only versions {} and higher".format(
                    ".".join(self._LOWEST_SCRIPT_MODE_VERSION)
                )
            )

        if "parameter_server" in distributions:
            enabled = distributions["parameter_server"].get("enabled", False)
            self._hyperparameters[self.LAUNCH_PS_ENV_NAME] = enabled

    def create_model(
        self, model_server_workers=None, role=None, vpc_config_override=VPC_CONFIG_DEFAULT
    ):
        """Create a SageMaker ``MXNetModel`` object that can be deployed to an ``Endpoint``.

        Args:
            role (str): The ``ExecutionRoleArn`` IAM Role ARN for the ``Model``, which is also used during
                transform jobs. If not specified, the role from the Estimator will be used.
            model_server_workers (int): Optional. The number of worker processes used by the inference server.
                If None, server will use one worker per vCPU.
            vpc_config_override (dict[str, list[str]]): Optional override for VpcConfig set on the model.
                Default: use subnets and security groups from this Estimator.
                * 'Subnets' (list[str]): List of subnet ids.
                * 'SecurityGroupIds' (list[str]): List of security group ids.

        Returns:
            sagemaker.mxnet.model.MXNetModel: A SageMaker ``MXNetModel`` object.
                See :func:`~sagemaker.mxnet.model.MXNetModel` for full details.
        """
        role = role or self.role
        return MXNetModel(
            self.model_data,
            role,
            self.entry_point,
            source_dir=self._model_source_dir(),
            enable_cloudwatch_metrics=self.enable_cloudwatch_metrics,
            name=self._current_job_name,
            container_log_level=self.container_log_level,
            code_location=self.code_location,
            py_version=self.py_version,
            framework_version=self.framework_version,
            image=self.image_name,
            model_server_workers=model_server_workers,
            sagemaker_session=self.sagemaker_session,
            vpc_config=self.get_vpc_config(vpc_config_override),
            dependencies=self.dependencies,
        )

    @classmethod
    def _prepare_init_params_from_job_description(cls, job_details, model_channel_name=None):
        """Convert the job description to init params that can be handled by the class constructor

        Args:
            job_details: the returned job details from a describe_training_job API call.
            model_channel_name (str): Name of the channel where pre-trained model data will be downloaded.

        Returns:
            dictionary: The transformed init_params

        """
        init_params = super(MXNet, cls)._prepare_init_params_from_job_description(
            job_details, model_channel_name
        )
        image_name = init_params.pop("image")
        framework, py_version, tag, _ = framework_name_from_image(image_name)

        if not framework:
            # If we were unable to parse the framework name from the image it is not one of our
            # officially supported images, in this case just add the image to the init params.
            init_params["image_name"] = image_name
            return init_params

        init_params["py_version"] = py_version

        # We switched image tagging scheme from regular image version (e.g. '1.0') to more expressive
        # containing framework version, device type and python version (e.g. '0.12-gpu-py2').
        # For backward compatibility map deprecated image tag '1.0' to a '0.12' framework version
        # otherwise extract framework version from the tag itself.
        init_params["framework_version"] = (
            "0.12" if tag == "1.0" else framework_version_from_tag(tag)
        )

        training_job_name = init_params["base_job_name"]

        if framework != cls.__framework_name__:
            raise ValueError(
                "Training job: {} didn't use image for requested framework".format(
                    training_job_name
                )
            )

        return init_params
