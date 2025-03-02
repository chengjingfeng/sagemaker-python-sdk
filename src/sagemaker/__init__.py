# Copyright 2017-2018 Amazon.com, Inc. or its affiliates. All Rights Reserved.
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

import pkg_resources

from sagemaker import estimator, parameter, tuner  # noqa: F401
from sagemaker.amazon.kmeans import KMeans, KMeansModel, KMeansPredictor  # noqa: F401
from sagemaker.amazon.pca import PCA, PCAModel, PCAPredictor  # noqa: F401
from sagemaker.amazon.lda import LDA, LDAModel, LDAPredictor  # noqa: F401
from sagemaker.amazon.linear_learner import (  # noqa: F401
    LinearLearner,
    LinearLearnerModel,
    LinearLearnerPredictor,
)
from sagemaker.amazon.factorization_machines import (  # noqa: F401
    FactorizationMachines,
    FactorizationMachinesModel,
)
from sagemaker.amazon.factorization_machines import FactorizationMachinesPredictor  # noqa: F401
from sagemaker.amazon.ntm import NTM, NTMModel, NTMPredictor  # noqa: F401
from sagemaker.amazon.randomcutforest import (  # noqa: F401
    RandomCutForest,
    RandomCutForestModel,
    RandomCutForestPredictor,
)
from sagemaker.amazon.knn import KNN, KNNModel, KNNPredictor  # noqa: F401
from sagemaker.amazon.object2vec import Object2Vec, Object2VecModel  # noqa: F401
from sagemaker.amazon.ipinsights import (  # noqa: F401
    IPInsights,
    IPInsightsModel,
    IPInsightsPredictor,
)

from sagemaker.algorithm import AlgorithmEstimator  # noqa: F401
from sagemaker.analytics import TrainingJobAnalytics, HyperparameterTuningJobAnalytics  # noqa: F401
from sagemaker.local.local_session import LocalSession  # noqa: F401

from sagemaker.model import Model, ModelPackage  # noqa: F401
from sagemaker.pipeline import PipelineModel  # noqa: F401
from sagemaker.predictor import RealTimePredictor  # noqa: F401
from sagemaker.session import Session  # noqa: F401
from sagemaker.session import container_def, pipeline_container_def  # noqa: F401
from sagemaker.session import production_variant  # noqa: F401
from sagemaker.session import s3_input  # noqa: F401
from sagemaker.session import get_execution_role  # noqa: F401

__version__ = pkg_resources.require("sagemaker")[0].version
