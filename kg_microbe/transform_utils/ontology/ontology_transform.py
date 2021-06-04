import os

from typing import Optional

from kgx.transformer import Transformer

from kg_microbe.transform_utils.transform import Transform


ONTOLOGIES = {
    #'HpTransform': 'hp.json',
    #'GoTransform': 'go-plus.json',
    'NCBITransform':  'ncbitaxon.json',
    'ChebiTransform': 'chebi.json',
    'EnvoTransform': 'envo.json',
    'GoTransform': 'go.json'
}


class OntologyTransform(Transform):
    """
    OntologyTransform parses an Obograph JSON form of an Ontology into nodes nad edges.

    """
    def __init__(self, input_dir: str = None, output_dir: str = None):
        source_name = "ontologies"
        super().__init__(source_name, input_dir, output_dir)

    def run(self, data_file: Optional[str] = None) -> None:
        """Method is called and performs needed transformations to process an ontology.

        :param data_file: data file to parse
        :return: None.
        """

        if data_file:
            k = data_file.split('.')[0]
            data_file = os.path.join(self.input_base_dir, data_file)
            self.parse(k, data_file, k)
        else:
            # load all ontologies
            for k in ONTOLOGIES.keys():
                data_file = os.path.join(self.input_base_dir, ONTOLOGIES[k])
                self.parse(k, data_file, k)

    def parse(self, name: str, data_file: str, source: str) -> None:
        """Processes the data_file.
        
        :param name: Name of the ontology
        :param data_file: data file to parse
        :param source: Source name
        :return: None.
        """

        print(f"Parsing {data_file}")
        transformer = Transformer()
        
        
        input_args = {
            'format': data_file.split('.')[-1],
            'filename': [data_file],
            'name': name
        }

        output_args = {
            'format': 'tsv',
            'filename': os.path.join(self.output_dir, name)
        }
        
        transformer.transform(input_args=input_args, output_args=output_args)
        transformer.save(output_args=output_args)
    
        '''transformer = ObographJsonTransformer()
        compression: Optional[str]
        if data_file.endswith('.gz'):
            compression = 'gz'
        else:
            compression = None
        transformer.parse(data_file, compression=compression, provided_by=source)
        output_transformer = PandasTransformer(transformer.graph)
        output_transformer.save(filename=os.path.join(self.output_dir, f'{name}'), output_format='tsv', mode=None)'''