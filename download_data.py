import click
from torch.hub import download_url_to_file
from torchvision.datasets.utils import extract_archive, download_and_extract_archive
import os 
import shutil

# TODO: add the others from https://www.mvtec.com/company/research/datasets/mvtec-ad/
data_url = {
    "bottle": "https://www.mydrive.ch/shares/38536/3830184030e49fe74747669442f0f282/download/420937370-1629951468/bottle.tar.xz",
    "carpet": "https://www.mydrive.ch/shares/38536/3830184030e49fe74747669442f0f282/download/420937484-1629951672/carpet.tar.xz",
    "leather": "https://www.mydrive.ch/shares/38536/3830184030e49fe74747669442f0f282/download/420937607-1629951964/leather.tar.xz"
}


@click.command()
@click.option('--categ', help= f"name of the subsets you want to download. Avaiable subsets: {', '.join(data_url.keys())}")
def download(categ):
    """Download the dataset MVTec AD and unzip the file into the data folder."""
    print(f"Downloading dataset: {categ}")
    if not os.path.exists("data"):
        os.makedirs("data")
    
    download_and_extract_archive(url=data_url[categ], download_root="data", remove_finished=True) 

    return 
    
if __name__ == '__main__':
    download()
