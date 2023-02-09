import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

with open('requirements.txt') as f:
    required = f.read().splitlines()

setuptools.setup(name='web3-proxy-providers',
                 version='0.1',
                 author='Sina Rezaei',
                 author_email='sinarezaei1991@gmail.com',
                 long_description_content_type="text/markdown",
                 long_description=long_description,
                 description='Proxy providers for web3py (Web3 python)',
                 url='https://github.com/sinarezaei/web3_proxy_providers',
                 license='MIT',
                 packages=setuptools.find_packages(),
                 classifiers=[
                     "Programming Language :: Python :: 3",
                     "License :: OSI Approved :: MIT License",
                     "Operating System :: OS Independent",
                 ],
                 install_requires=required,
                 python_requires='>=3.6',
                 zip_safe=False)
