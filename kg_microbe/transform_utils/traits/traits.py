import csv
import re
import os
from typing import Dict, List, Optional
from collections import defaultdict

from kg_microbe.transform_utils.transform import Transform
from kg_microbe.utils.transform_utils import parse_header, parse_line, write_node_edge_item

from kg_microbe.utils.nlp_utils import *
from kg_microbe.utils.robot_utils import *

from kgx.cli.cli_utils import transform


class TraitsTransform(Transform):

    """
    Ingest traits dataset (NCBI/GTDB)

    Essentially just ingests and transforms this file:
    https://github.com/bacteria-archaea-traits/bacteria-archaea-traits/blob/master/output/condensed_traits_NCBI.csv

    And extracts the following columns:
        - tax_id
        - org_name
        - metabolism
        - pathways
        - shape
        - carbon_substrates
        - cell_shape
        - isolation_source
    
    Also implements:
        -   OGER to run NLP via the 'nlp_utils' module and 
        -   ROBOT using 'robot_utils' module.
    """

    def __init__(self, input_dir: str = None, output_dir: str = None, nlp = True) -> None:
        '''
        Initialize TraitsTransform Class

        :param input_dir: Input file path (str)
        :param output_dir: Output file path (str)

        '''
        source_name = "condensed_traits_NCBI"
        super().__init__(source_name, input_dir, output_dir, nlp)  # set some variables

        self.node_header = ['id', 'name', 'category', 'match_description']
        self.edge_header = ['subject', 'predicate', 'object', 'relation']
        self.nlp = nlp

    def run(self, data_file: Optional[str] = None):
        """
        Method is called and performs needed transformations to process the 
        trait data (NCBI/GTDB).
        
        :param data_file: Input file name.
        """
        
        if data_file is None:
            data_file = self.source_name + ".csv"
        
        input_file = os.path.join(
            self.input_base_dir, data_file)
            
        # make directory in data/transformed
        os.makedirs(self.output_dir, exist_ok=True)

        """
        Import SSSOM 
        """
        sssom_columns = ['subject_label', 'object_id', 'object_label', 'object_match_field', 'match_category']
        chem_sssom = pd.read_csv(self.chemicals_sssom, sep='\t', low_memory=False, comment='#', usecols=sssom_columns)
        chem_sssom['subject_label'] = chem_sssom['subject_label'].str.replace(r"[\'\",]","",regex=True)

        path_sssom = pd.read_csv(self.pathways_sssom, sep='\t', low_memory=False, comment='#', usecols=sssom_columns)
        path_sssom['subject_label'] = path_sssom['subject_label'].str.replace(r"[\'\",]","",regex=True).str.replace('_',' ')

        """
        Implement ROBOT 
        """
        # Convert OWL to JSON for CheBI Ontology
        convert_to_json(self.input_base_dir, 'CHEBI')
        #convert_to_json(self.input_base_dir, 'ECOCORE')

        # Extract the 'cellular organisms' tree from NCBITaxon and convert to JSON
        '''
        NCBITaxon_131567 = cellular organisms 
        (Source = http://www.ontobee.org/ontology/NCBITaxon?iri=http://purl.obolibrary.org/obo/NCBITaxon_131567)
        '''
        #subset_ontology_needed = 'NCBITaxon'
        #extract_convert_to_json(self.input_base_dir, subset_ontology_needed, 'NCBITaxon:131567', 'TOP')


        """
        Get information from the EnvironemtTransform
        """
        environment_file = os.path.join(self.input_base_dir, 'environments.csv')
        env_df = pd.read_csv(environment_file, sep=',', low_memory=False, usecols=['Type', 'ENVO_terms', 'ENVO_ids'])
        unique_env_df = env_df.drop_duplicates()
        

        """
        Create termlist.tsv files from ontology JSON files for NLP
        TODO: Replace this code once runNER is installed and remove 'kg_microbe/utils/biohub_converter.py'
        """
        create_termlist(self.input_base_dir, 'chebi')
        #create_termlist(self.input_base_dir, 'ecocore')
        create_termlist(self.input_base_dir, 'go')
        

        """
        NLP: Get 'chem_node_type' and 'org_to_chem_edge_label'
        """
        if self.nlp:
            # Prep for NLP. Make sure the first column is the ID
            # CHEBI
            cols_for_nlp = ['tax_id', 'carbon_substrates']
            input_file_name = prep_nlp_input(input_file, cols_for_nlp, 'CHEBI')
            # Set-up the settings.ini file for OGER and run
            create_settings_file(self.nlp_dir, 'CHEBI')
            oger_output_chebi = run_oger(self.nlp_dir, input_file_name, n_workers=5)
            oger_output_chebi_not_exact_match = oger_output_chebi[oger_output_chebi['StringMatch'] != 'Exact']

            # GO
            cols_for_nlp = ['tax_id', 'pathways']
            input_file_name = prep_nlp_input(input_file, cols_for_nlp, 'GO')
            # Set-up the settings.ini file for OGER and run
            create_settings_file(self.nlp_dir, 'GO')
            oger_output_go = run_oger(self.nlp_dir, input_file_name, n_workers=5)
            oger_output_go_not_exact_match = oger_output_go[oger_output_go['StringMatch'] != 'Exact']
            
            '''# ECOCORE
            cols_for_nlp = ['tax_id', 'metabolism']
            input_file_name = prep_nlp_input(input_file, cols_for_nlp, 'ECOCORE')
            # Set-up the settings.ini file for OGER and run
            create_settings_file(self.nlp_dir, 'ECOCORE')
            oger_output_ecocore = run_oger(self.nlp_dir, input_file_name, n_workers=5)
            #oger_output = process_oger_output(self.nlp_dir, input_file_name)'''
        
        # Mapping table for metabolism.
        # TODO: Find an alternative way for doing this
        col = ['ID', 'ActualTerm', 'PreferredTerm']
        metabolism_map_df = pd.DataFrame(columns=col)
        metabolism_map_df = metabolism_map_df.append({'ID':'ECOCORE:00000172', 'ActualTerm':'anaerobic', 'PreferredTerm':'anaerobe'}, ignore_index=True)
        metabolism_map_df = metabolism_map_df.append({'ID':'ECOCORE:00000172', 'ActualTerm':'strictly anaerobic', 'PreferredTerm':'anaerobe'}, ignore_index=True)
        metabolism_map_df = metabolism_map_df.append({'ID':'ECOCORE:00000178', 'ActualTerm':'obligate anaerobic', 'PreferredTerm':'obligate anaerobe'}, ignore_index=True)
        metabolism_map_df = metabolism_map_df.append({'ID':'ECOCORE:00000177', 'ActualTerm':'facultative', 'PreferredTerm':'facultative anaerobe'}, ignore_index=True)
        metabolism_map_df = metabolism_map_df.append({'ID':'ECOCORE:00000179', 'ActualTerm':'obligate aerobic', 'PreferredTerm':'obligate aerobe'}, ignore_index=True)
        metabolism_map_df = metabolism_map_df.append({'ID':'ECOCORE:00000173', 'ActualTerm':'aerobic', 'PreferredTerm':'aerobe'}, ignore_index=True)
        metabolism_map_df = metabolism_map_df.append({'ID':'ECOCORE:00000180', 'ActualTerm':'microaerophilic', 'PreferredTerm':'microaerophilic'}, ignore_index=True)


        # transform data, something like:
        with open(input_file, 'r') as f, \
                open(self.output_node_file, 'w') as node, \
                open(self.output_edge_file, 'w') as edge, \
                open(self.subset_terms_file, 'w') as terms_file:   # If need to capture CURIEs for ROBOT STAR extraction

            # write headers (change default node/edge headers if necessary
            node.write("\t".join(self.node_header) + "\n")
            edge.write("\t".join(self.edge_header) + "\n")
            
            header_items = parse_header(f.readline(), sep=',')
            seen_node: dict = defaultdict(int)
            seen_edge: dict = defaultdict(int)


            # Nodes
            org_node_type = "biolink:OrganismTaxon" # [org_name]
            chem_node_type = "biolink:ChemicalSubstance" # [carbon_substrate]
            shape_node_type = "biolink:AbstractEntity" # [cell_shape]
            metabolism_node_type = "biolink:ActivityAndBehavior" # [metabolism]
            pathway_node_type = "biolink:BiologicalProcess" # [pathways]
            curie = 'NEED_CURIE'
            
            #Prefixes
            org_prefix = "NCBITaxon:"
            chem_prefix = "microtraits.carbon_substrates:"
            shape_prefix = "microtraits.cell_shape_enum:"
            #metab_prefix = "microtraits.metabolism:"
            source_prefix = "microtraits.data_source:"
            pathway_prefix = "microtraits.pathways:"

            # Edges
            org_to_shape_edge_label = "biolink:has_phenotype" #  [org_name -> cell_shape, metabolism]
            org_to_shape_edge_relation = "RO:0002200" #  [org_name -> has phenotype -> cell_shape, metabolism]
            org_to_chem_edge_label = "biolink:interacts_with" # [org_name -> carbon_substrate]
            org_to_chem_edge_relation = "RO:0002438" # [org_name -> 'trophically interacts with' -> carbon_substrate]
            org_to_source_edge_label = "biolink:location_of" # [org -> isolation_source]
            org_to_source_edge_relation = "RO:0001015" #[org -> location_of -> source]
            org_to_metab_edge_label = "biolink:capable_of" # [org -> metabolism]
            org_to_metab_edge_relation = "RO:0002215" # [org -> biological_process -> metabolism]
            org_to_pathway_edge_label = "biolink:capable_of" # # [org -> pathway]
            org_to_pathway_edge_relation = "RO:0002215" # [org -> biological_process -> metabolism]

            ''' TEST
                Collector of partial and NoMatches.
            '''
            remnants_chebi = pd.DataFrame()
            remnants_path = pd.DataFrame()
            
            # transform
            for line in f:
                """
                This dataset is a csv and also has commas 
                present within a column of data. 
                Hence a regex solution
                """
                # transform line into nodes and edges
                # node.write(this_node1)
                # node.write(this_node2)
                # edge.write(this_edge)
                

                line = re.sub(r'(?!(([^"]*"){2})*[^"]*$),', '|', line) # alanine, glucose -> alanine| glucose
                items_dict = parse_line(line, header_items, sep=',')
                match_description = ''

                org_name = items_dict['org_name']
                tax_id = items_dict['tax_id']
                metabolism = items_dict['metabolism']
                carbon_substrates = set([x.strip() for x in items_dict['carbon_substrates'].split('|')])
                cell_shape = items_dict['cell_shape']
                isolation_source = set([x.strip() for x in items_dict['isolation_source'].split('|')])
                pathways = set([x.strip() for x in items_dict['pathways'].replace('_',' ').split('|')])

            # Write Node ['id', 'entity', 'category']
                # Write organism node 
                org_id = org_prefix + str(tax_id)
                if not org_id.endswith(':na') and org_id not in seen_node:
                    write_node_edge_item(fh=node,
                                         header=self.node_header,
                                         data=[org_id,
                                               org_name,
                                               org_node_type,
                                               match_description])
                    seen_node[org_id] += 1
                    # If capture of all NCBITaxon: CURIEs are needed for ROBOT STAR extraction
                    if org_id.startswith('NCBITaxon:'):
                        terms_file.write(org_id + "\n")

                # Write chemical node
                for chem_name in carbon_substrates:
                    chem_curie = curie
                    multi_row_flag = False
                    match_description = ''
                    #chem_node_type = chem_name

                    # Get relevant NLP results
                    if chem_name != 'NA':
                        relevant_tax = oger_output_chebi.loc[oger_output_chebi['TaxId'] == int(tax_id)]
                        relevant_chem = relevant_tax.loc[relevant_tax['TokenizedTerm'] == chem_name]
                        # Check if term exists
                        if len(relevant_chem) >= 1:
                            # 'Exact' string match 
                            if any(relevant_chem['StringMatch'].str.contains('Exact')):
                                chem_curie = relevant_chem['CURIE'].loc[relevant_chem['StringMatch']=='Exact'].item()
                                chem_node_type = relevant_chem['Biolink'].loc[relevant_chem['StringMatch']=='Exact'].item()
                                match_description = 'ExactStringMatch'
                            # 'Partial' or 'No Match'
                            else:
                                chem_ner_sssom = relevant_chem.merge(chem_sssom, how='inner', left_on=['TokenizedTerm', 'CURIE'], right_on=['subject_label', 'object_id'])
                                chem_ner_sssom = chem_ner_sssom.drop_duplicates()
                                # If 'oio:hasExactSynonym' present
                                if any(chem_ner_sssom['object_match_field'].str.contains('oio:hasExactSynonym')):
                                    chem_curie = chem_ner_sssom['CURIE'].loc[chem_ner_sssom['object_match_field'] == 'oio:hasExactSynonym'].item()
                                    chem_node_type = chem_ner_sssom['Biolink'].loc[chem_ner_sssom['object_match_field'] == 'oio:hasExactSynonym'].item()
                                    match_description = chem_ner_sssom['object_match_field'].loc[chem_ner_sssom['object_match_field'] == 'oio:hasExactSynonym'].item()
                                # if 'oio:hasRelatedSynonym' present
                                elif any(chem_ner_sssom['object_match_field'].str.contains('oio:hasRelatedSynonym')):
                                    if len(chem_ner_sssom['CURIE'].loc[chem_ner_sssom['object_match_field'] == 'oio:hasRelatedSynonym']) > 1:
                                        multi_row_flag = True
                                        chem_curie = chem_ner_sssom['CURIE'].loc[chem_ner_sssom['object_match_field'] == 'oio:hasRelatedSynonym']
                                        chem_node_type = chem_ner_sssom['Biolink'].loc[chem_ner_sssom['object_match_field'] == 'oio:hasRelatedSynonym']
                                        match_description = chem_ner_sssom['object_match_field'].loc[chem_ner_sssom['object_match_field'] == 'oio:hasRelatedSynonym']
                                    else:
                                        chem_curie = chem_ner_sssom['CURIE'].loc[chem_ner_sssom['object_match_field'] == 'oio:hasRelatedSynonym'].item()
                                        chem_node_type = chem_ner_sssom['Biolink'].loc[chem_ner_sssom['object_match_field'] == 'oio:hasRelatedSynonym'].item()
                                        match_description = chem_ner_sssom['object_match_field'].loc[chem_ner_sssom['object_match_field'] == 'oio:hasRelatedSynonym'].item()
                                else:
                                    remnants_chebi = remnants_chebi.append(chem_ner_sssom,ignore_index=True)
                                    #chem_curie = relevant_chem.iloc[0]['CURIE']
                                    #chem_node_type = relevant_chem.iloc[0]['Biolink']
                                
                                
                    if multi_row_flag == True:
                        for i,v in chem_curie.items():
                            if chem_curie[i] == curie:
                                chem_id = chem_prefix + chem_name.lower().replace(' ','_')
                            else:
                                chem_id = chem_curie[i]
                            if  not chem_id.endswith(':na') and chem_id not in seen_node:
                                write_node_edge_item(fh=node,
                                                    header=self.node_header,
                                                    data=[chem_id,
                                                        chem_name,
                                                        chem_node_type[i],
                                                        match_description[i]])
                                seen_node[chem_id] += 1
                        
                    else:
                        if chem_curie == curie:
                            chem_id = chem_prefix + chem_name.lower().replace(' ','_')
                        else:
                            chem_id = chem_curie
                            
                        if  not chem_id.endswith(':na') and  chem_id not in seen_node:
                            write_node_edge_item(fh=node,
                                                header=self.node_header,
                                                data=[chem_id,
                                                    chem_name,
                                                    chem_node_type,
                                                    match_description])
                            seen_node[chem_id] += 1

                # Write shape node
                '''# Get relevant NLP results
                if cell_shape != 'NA':
                    relevant_tax = oger_output_pato.loc[oger_output_pato['TaxId'] == int(tax_id)]
                    relevant_shape = relevant_tax.loc[relevant_tax['TokenizedTerm'] == cell_shape]
                    if len(relevant_shape) == 1:
                        cell_shape = relevant_shape.iloc[0]['CURIE']
                        shape_node_type = relevant_shape.iloc[0]['Biolink']'''
                        
                shape_id = shape_prefix + cell_shape.lower()

                if  not shape_id.endswith(':na') and shape_id not in seen_node:
                    write_node_edge_item(fh=node,
                                         header=self.node_header,
                                         data=[shape_id,
                                               cell_shape,
                                               shape_node_type,
                                               match_description])
                    seen_node[shape_id] += 1

                # Write source node
                for source_name in isolation_source:
                    #   Collapse the entity
                    #   A_B_C_D => [A, B, C, D]
                    #   D is the entity of interest
                    source_name_split = source_name.split('_')
                    source_name_collapsed = source_name_split[-1]
                    env_curie = curie
                    env_term = source_name_collapsed
                    source_node_type = "" # [isolation_source] left blank intentionally
                    match_description = ''

                    # Get information from the environments.csv (unique_env_df)
                    relevant_env_df = unique_env_df.loc[unique_env_df['Type'] == source_name]

                    if len(relevant_env_df) == 1:
                            '''
                            If multiple ENVOs exist, take the last one since that would be the curie of interest
                            after collapsing the entity.
                            TODO(Maybe): If CURIE is 'nan', it could be sourced from OGER o/p (ENVO backend)
                                  of environments.csv
                            '''
                            env_curie = str(relevant_env_df.iloc[0]['ENVO_ids']).split(',')[-1].strip()
                            env_term = str(relevant_env_df.iloc[0]['ENVO_terms']).split(',')[-1].strip()
                            if env_term == 'nan':
                                env_curie = curie
                                env_term = source_name_collapsed
                            
                                 

                    #source_id = source_prefix + source_name.lower()
                    if env_curie == curie:
                        source_id = source_prefix + source_name_collapsed.lower()
                    else:
                        source_id = env_curie
                        if source_id.startswith('CHEBI:'):
                            source_node_type = chem_node_type

                    if  not source_id.endswith(':na') and source_id not in seen_node:
                        write_node_edge_item(fh=node,
                                            header=self.node_header,
                                            data=[source_id,
                                                env_term,
                                                source_node_type,
                                                match_description])
                        seen_node[source_id] += 1
                    
                # Write metabolism node

                metabolism_id = None
                
                if metabolism != 'NA':
                    if metabolism_map_df['ActualTerm'].str.contains(metabolism).any():
                        metabolism_id = metabolism_map_df.loc[metabolism_map_df['ActualTerm'] == metabolism]['ID'].item()
                        metabolism_term = metabolism_map_df.loc[metabolism_map_df['ActualTerm'] == metabolism]['PreferredTerm'].item()
                        if metabolism_id not in seen_node:
                            write_node_edge_item(fh=node,
                                                header=self.node_header,
                                                data=[metabolism_id,
                                                    metabolism_term,
                                                    metabolism_node_type,
                                                    match_description])
                            seen_node[metabolism_id] += 1

                # Write pathway node 
                for pathway_name in pathways:
                    pathway_curie = curie
                    match_description = ''
                    multi_row_flag = False

                    # Get relevant NLP results
                    if pathway_name != 'NA':
                        relevant_tax = oger_output_go.loc[oger_output_go['TaxId'] == int(tax_id)]
                        relevant_pathway = relevant_tax.loc[relevant_tax['TokenizedTerm'] == pathway_name]
                        if len(relevant_pathway) >= 1:
                            # 'Exact' string match 
                            if any(relevant_pathway['StringMatch'].str.contains('Exact')):
                                pathway_curie = relevant_pathway['CURIE'].loc[relevant_pathway['StringMatch']=='Exact'].item()
                                pathway_node_type = relevant_pathway['Biolink'].loc[relevant_pathway['StringMatch']=='Exact'].item()
                                match_description = 'ExactStringMatch'
                            # 'Partial' or 'No Match'
                            else:
                                path_ner_sssom = relevant_pathway.merge(path_sssom, how='inner', left_on=['TokenizedTerm', 'CURIE'], right_on=['subject_label', 'object_id'])
                                path_ner_sssom = path_ner_sssom.drop_duplicates()
                                # If 'oio:hasExactSynonym' present
                                if any(path_ner_sssom['object_match_field'].str.contains('oio:hasExactSynonym')):
                                    pathway_curie = path_ner_sssom['CURIE'].loc[path_ner_sssom['object_match_field'] == 'oio:hasExactSynonym'].item()
                                    pathway_node_type = path_ner_sssom['Biolink'].loc[path_ner_sssom['object_match_field'] == 'oio:hasExactSynonym'].item()
                                    match_description = path_ner_sssom['object_match_field'].loc[path_ner_sssom['object_match_field'] == 'oio:hasExactSynonym'].item()
                                # if 'oio:hasRelatedSynonym' present
                                elif any(path_ner_sssom['object_match_field'].str.contains('oio:hasRelatedSynonym')):
                                    if len(path_ner_sssom['CURIE'].loc[path_ner_sssom['object_match_field'] == 'oio:hasRelatedSynonym']) > 1:
                                        multi_row_flag = True
                                        pathway_curie = path_ner_sssom['CURIE'].loc[path_ner_sssom['object_match_field'] == 'oio:hasRelatedSynonym']
                                        pathway_node_type = path_ner_sssom['Biolink'].loc[path_ner_sssom['object_match_field'] == 'oio:hasRelatedSynonym']
                                        match_description = path_ner_sssom['object_match_field'].loc[path_ner_sssom['object_match_field'] == 'oio:hasRelatedSynonym']
                                    else:
                                        pathway_curie = path_ner_sssom['CURIE'].loc[path_ner_sssom['object_match_field'] == 'oio:hasRelatedSynonym'].item()
                                        pathway_node_type = path_ner_sssom['Biolink'].loc[path_ner_sssom['object_match_field'] == 'oio:hasRelatedSynonym'].item()
                                        match_description = path_ner_sssom['object_match_field'].loc[path_ner_sssom['object_match_field'] == 'oio:hasRelatedSynonym'].item()
                                # if 'oio:hasBroadSynonym' present
                                elif any(path_ner_sssom['object_match_field'].str.contains('oio:hasBroadSynonym')):
                                    if len(path_ner_sssom['CURIE'].loc[path_ner_sssom['object_match_field'] == 'oio:hasBroadSynonym']) > 1:
                                        multi_row_flag = True
                                        pathway_curie = path_ner_sssom['CURIE'].loc[path_ner_sssom['object_match_field'] == 'oio:hasBroadSynonym']
                                        pathway_node_type = path_ner_sssom['Biolink'].loc[path_ner_sssom['object_match_field'] == 'oio:hasBroadSynonym']
                                        match_description = path_ner_sssom['object_match_field'].loc[path_ner_sssom['object_match_field'] == 'oio:hasBroadSynonym']
                                    else:
                                        pathway_curie = path_ner_sssom['CURIE'].loc[path_ner_sssom['object_match_field'] == 'oio:hasBroadSynonym'].item()
                                        pathway_node_type = path_ner_sssom['Biolink'].loc[path_ner_sssom['object_match_field'] == 'oio:hasBroadSynonym'].item()
                                        match_description = path_ner_sssom['object_match_field'].loc[path_ner_sssom['object_match_field'] == 'oio:hasBroadSynonym'].item()
                                else:
                                    remnants_path = remnants_path.append(path_ner_sssom,ignore_index=True)

                    if multi_row_flag == True:
                        for i,v in pathway_curie.items():
                            if pathway_curie[i] == curie:
                                pathway_id = pathway_prefix + pathway_name.lower().replace(' ','_')
                            else:
                                pathway_id = pathway_curie[i]
                            if  not pathway_id.endswith(':na') and pathway_id not in seen_node:
                                write_node_edge_item(fh=node,
                                                    header=self.node_header,
                                                    data=[pathway_id,
                                                        pathway_name,
                                                        pathway_node_type[i],
                                                        match_description[i]])
                                seen_node[pathway_id] += 1
                        multi_row_flag = False
                    else:
                        if pathway_curie == curie:
                            pathway_id = pathway_prefix + pathway_name.lower().replace(' ','_')
                        else:
                            pathway_id = pathway_curie

                        
                        if  not pathway_id.endswith(':na') and  pathway_id not in seen_node:
                            write_node_edge_item(fh=node,
                                                header=self.node_header,
                                                data=[pathway_id,
                                                    pathway_name,
                                                    pathway_node_type,
                                                    match_description])
                            seen_node[pathway_id] += 1
               
                


            # Write Edge
                # org-chem edge
                if not chem_id.endswith(':na') and org_id+chem_id not in seen_edge:
                    write_node_edge_item(fh=edge,
                                            header=self.edge_header,
                                            data=[org_id,
                                                org_to_chem_edge_label,
                                                chem_id,
                                                org_to_chem_edge_relation])
                    seen_edge[org_id+chem_id] += 1

                # org-shape edge
                if  not shape_id.endswith(':na') and org_id+shape_id not in seen_edge:
                    write_node_edge_item(fh=edge,
                                            header=self.edge_header,
                                            data=[org_id,
                                                org_to_shape_edge_label,
                                                shape_id,
                                                org_to_shape_edge_relation])
                    seen_edge[org_id+shape_id] += 1
                
                # org-source edge
                if not source_id.endswith(':na') and org_id+source_id not in seen_edge:
                    write_node_edge_item(fh=edge,
                                            header=self.edge_header,
                                            data=[org_id,
                                                org_to_source_edge_label,
                                                source_id,
                                                org_to_source_edge_relation])
                    seen_edge[org_id+source_id] += 1

                # org-metabolism edge
                if metabolism_id != None and not metabolism_id.endswith(':na') and org_id+metabolism_id not in seen_edge:
                    write_node_edge_item(fh=edge,
                                            header=self.edge_header,
                                            data=[org_id,
                                                org_to_metab_edge_label,
                                                metabolism_id,
                                                org_to_metab_edge_relation])
                    seen_edge[org_id+metabolism_id] += 1

                # org-pathway edge
                if pathway_id != None and not pathway_id.endswith(':na') and org_id+pathway_id not in seen_edge:
                    write_node_edge_item(fh=edge,
                                            header=self.edge_header,
                                            data=[org_id,
                                                org_to_pathway_edge_label,
                                                pathway_id,
                                                org_to_pathway_edge_relation])
                    seen_edge[org_id+source_id] += 1

        # Files write ends
        remnants_chebi.to_csv(os.path.join(self.DEFAULT_NLP_OUTPUT_DIR,'remnantsCHEBI.tsv'), sep='\t', index=False)
        remnants_path.to_csv(os.path.join(self.DEFAULT_NLP_OUTPUT_DIR,'remnantsGO.tsv'), sep='\t', index=False)

        # Get trees from all relevant IDs from NCBITaxon and convert to JSON
        '''
        NCBITaxon_131567 = cellular organisms 
        (Source = http://www.ontobee.org/ontology/NCBITaxon?iri=http://purl.obolibrary.org/obo/NCBITaxon_131567)
        '''
        subset_ontology_needed = 'NCBITaxon'
        extract_convert_to_json(self.input_base_dir, subset_ontology_needed, self.subset_terms_file, 'BOT')