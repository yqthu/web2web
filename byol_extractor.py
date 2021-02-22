from stable_baselines3.common.torch_layers import BaseFeaturesExtractor
from stable_baselines3.common.preprocessing import is_image_space
import torch.nn as nn
import torch
from torchvision import models
import gym

class ByolCNN(BaseFeaturesExtractor):
    def __init__(self, observation_space: gym.spaces.Box, features_dim: int = 512):
        super(ByolCNN, self).__init__(observation_space, features_dim)
        assert is_image_space(observation_space)
        pf = 'learner.target_encoder.net.'
        pretrained = torch.load('lightning_logs/version_4/checkpoints/epoch=69-step=1079962.ckpt')
        # pretrained = torch.load('/tmp/a.ckpt', map_location=torch.device('cpu'))
        n_input_channels = observation_space.shape[0]
        self.cnn = models.resnet50(pretrained=False)
        self.cnn.load_state_dict({k[len(pf):]: v for k, v in pretrained['state_dict'].items() if k.startswith(pf)})

        # Compute shape by doing one forward pass
        with torch.no_grad():
            n_flatten = self.cnn(torch.as_tensor(observation_space.sample()[None]).float()).shape[1]

        self.linear = nn.Sequential(nn.Linear(n_flatten, features_dim), nn.ReLU())

    def forward(self, observations: torch.Tensor) -> torch.Tensor:
        return self.linear(self.cnn(observations))