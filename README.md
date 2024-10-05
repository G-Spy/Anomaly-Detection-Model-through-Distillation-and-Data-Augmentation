# STPM-Augmented-for-industrial-anomaly-detection

## Linked projects
Code forked from [hcw-00/STPM_pytorch_lightning](https://github.com/hcw-00/STPM_pytorch_lightning)

[Not yet added] Knowledge distilation for UNet: [VaticanCameos99/knowledge-distillation-for-unet](https://github.com/VaticanCameos99/knowledge-distillation-for-unet)

Related paper: https://arxiv.org/pdf/1812.00249.pdf 

## Starting the environment.
The `.devcontainer` folder in the repository allows to create a development environment that allows compatibility when using the project on yonsei's servers or locally. There are three ways to run the code. Use Visual Studio Code as editor.
> Note: the first time that you start the container is slower. It has to download the image and the python requirements and cache them.

### GPU or CPU ? 
Look at these two lines in the file `.devcontainer.devcontainer.json` :
```
"image": "ufoym/deepo:pytorch-py38-cpu", // Size: 530.18 MB
//"image": "ufoym/deepo:pytorch-py38", // size: 5.86 GB
```
Comment the right line depending on the your setup. If you want to use your GPU (which is necessary for training) it will takes more time to download the image, but then it is cached on your computer.

### Running in Github Codespaces.
Simply click on the following button:

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://github.com/codespaces/new?hide_repo_select=true&ref=main&repo=568728944&machine=basicLinux32gb&devcontainer_path=.devcontainer%2Fdevcontainer.json&location=SouthEastAsia)

### Running locally
1. Clone it.
2. Docker has to be running on your computer.
3. Download the dev containers extension for vscode.

![image](https://user-images.githubusercontent.com/23149720/203073967-f3cf7a6f-056e-424b-b96b-883af4ff2a29.png)

5. Start the container 

![image](https://code.visualstudio.com/assets/docs/devcontainers/create-dev-container/dev-containers-reopen.png)

[More info](https://code.visualstudio.com/docs/devcontainers/create-dev-container)

### Using conda
Another way to create the environment is to use conda. For example, when training the model on [AWS Sagemaker Studio Lab](studiolab.sagemaker.aws) (for free) then you can't launch the devcontainer.  They only use JupyterLab as user interface and we need VSCode to use the devcontainers. The solution is to create a conda env by running the following command:

```
conda env create -f conda_env.yml
```

and then,

```
conda activate stpm
```

## Downloading the dataset.
The dataset is directly downloaded from the link found on the [**MVTEC site**](https://www.mvtec.com/company/research/datasets/mvtec-ad/).

To download a subset of the dataset, run the following python code.
```bash
python download_data.py --categ NAME
```
Replace `NAME` with the data you want (example "carpet"). Too see the data use the "--help" argument.

## Usage

```
python train_resnet.py --phase train --category bottle
```

> I tested and it takes approx. 7 min to train the model with Tesla T4 GPU on AWS Sagemaker Studio Lab.



### WandB
When running the code, it will automatically ask you to connect to your WandB account (you have to create one). And then you can observe the metrics on the project's page: [https://wandb.ai/stpm-unet/STPM/runs](https://wandb.ai/stpm-unet/STPM/runs)

WandB also keeps the source code of the run. So, if we want to see an old model and the code related to it, we can obtain it using the WandB website.
