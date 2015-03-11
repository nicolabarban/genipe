
# This file is part of gwip.
#
# This work is licensed under the Creative Commons Attribution-NonCommercial
# 4.0 International License. To view a copy of this license, visit
# http://creativecommons.org/licenses/by-nc/4.0/ or send a letter to Creative
# Commons, PO Box 1866, Mountain View, CA 94042, USA.


import random
import unittest
from tempfile import TemporaryDirectory

import patsy
import numpy as np
import pandas as pd
from pkg_resources import resource_filename

from ..tools.imputed_stats import *
from ..tools.imputed_stats import _get_result_from_linear_logistic


__author__ = "Louis-Philippe Lemieux Perreault"
__copyright__ = "Copyright 2014, Beaulieu-Saucier Pharmacogenomics Centre"
__license__ = "Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)"


__all__ = ["TestImputedStats"]


def reverse_dosage(dosage):
    """Finds values for d1, d2 and d3 from dosage."""
    d1, d2, d3 = 0, 0, 0
    if np.isnan(dosage):
        d1 = random.uniform(0.5, 0.8)
        d2 = random.uniform(0, 0.2)
        d3 = 1 - d1 - d2

    elif dosage == 1:
        d1 = 0
        d2 = dosage
        d3 = 0

    elif dosage < 1:
        d2 = dosage
        d1 = 1 - d2
        d3 = 0

    elif dosage > 1.5:
        d1 = 0
        d3 = random.uniform(0.98, 1)
        d2 = ((dosage / 2) - d3) * 2

    else:
        d1 = 0
        d2 = random.uniform(0.98, 1)
        d3 = (dosage - d2) / 2

    return d1, d2, d3


def create_input_files(i_filename, output_dirname, analysis_type,
                       pheno_name="y", interaction=None, nb_process=None):
    """Creates input files for the imputed_stats script."""
    # Reading the data
    data = pd.read_csv(i_filename, sep="\t", compression="bz2")

    # Adding a sample column
    data["sample_id"] = ["sample_{}".format(i+1) for i in range(len(data))]

    # Saving the phenotypes to file
    pheno_filename = os.path.join(output_dirname, "phenotypes.txt")
    data.to_csv(pheno_filename, sep="\t", index=False, na_rep="999999")

    # Creating the sample file
    sample_filename = os.path.join(output_dirname, "samples.txt")
    with open(sample_filename, "w") as o_file:
        print("ID_1 ID_2 missing father mother sex plink_pheno", file=o_file)
        print("0 0 0 D D D B", file=o_file)
        for sample, gender in data[["sample_id", "gender"]].values:
            print(sample, sample, "0", "0", "0", gender, "-9", file=o_file)

    # Creating the IMPUTE2 file
    impute2_filename = os.path.join(output_dirname, "impute2.txt")
    with open(impute2_filename, "w") as o_file:
        print("22 marker_1 1 T C", end="", file=o_file)
        for dosage in data.snp1.values:
            d1, d2, d3 = reverse_dosage(dosage)
            print("", d1, d2, d3, sep=" ", end="", file=o_file)
        print(file=o_file)

        print("22 marker_2 2 G A", end="", file=o_file)
        for dosage in data.snp2.values:
            d1, d2, d3 = reverse_dosage(dosage)
            print("", d1, d2, d3, sep=" ", end="", file=o_file)
        print(file=o_file)

        print("22 marker_3 3 AT A", end="", file=o_file)
        for dosage in data.snp3.values:
            d1, d2, d3 = reverse_dosage(dosage)
            print("", d1, d2, d3, sep=" ", end="", file=o_file)
        print(file=o_file)

    # The prefix of the output files
    o_prefix = os.path.join(output_dirname, "test_imputed_stats_linear")

    # The tool's options
    options = [
        analysis_type,
        "--impute2", impute2_filename,
        "--sample", sample_filename,
        "--pheno", pheno_filename,
        "--out", o_prefix,
        "--gender-column", "gender",
        "--covar", "C1,C2,C3,age,gender",
        "--missing-value", "999999",
        "--sample-column", "sample_id",
        "--pheno-name", pheno_name,
    ]

    # Is there interaction?
    if interaction is not None:
        options.extend(["--interaction", interaction])

    # Multi processes are required?
    if nb_process is not None:
        options.extend(["--nb-process", str(nb_process)])

    return o_prefix, options


class TestImputedStats(unittest.TestCase):

    @staticmethod
    def clean_logging_handlers():
        handlers = list(logging.root.handlers)
        for handler in handlers:
            logging.root.removeHandler(handler)

    def setUp(self):
        """Setup the tests."""
        # Creating the temporary directory
        self.output_dir = TemporaryDirectory(prefix="gwip_test_")

    def tearDown(self):
        """Finishes the test."""
        # Deleting the output directory
        self.output_dir.cleanup()

    def test_read_phenotype(self):
        """Tests the 'read_phenotype' function."""
        # A dummy object for options
        class Dummy(object):
            pass

        # The content of the phenotype file
        phenotype_content = (
            "sample_id\tTime_To_Event\tCensure\tC1\tC2\tC3\tC4\tGender\t"
            "Pheno_Lin\tPheno_Logit\tInter\n"
            "sample_1\t10\t0\t0.3\t0.2\t0.45\t0.01\t1\t0.01\t0\t0.00001\n"
            "sample_2\t2\t1\t0.9\t0.1\t0.42\t0.012\t2\t0.15\t1\t0.00332\n"
            "sample_3\t8\t1\t0.4\t0.67\t999\t0.001\t1\t0.0\t0\t0.000001\n"
        )
        filename = os.path.join(self.output_dir.name, "phenotypes.txt")
        with open(filename, "w") as o_file:
            o_file.write(phenotype_content)

        # Need an object for the function's option
        args = Dummy()
        args.missing_value = None
        args.sample_column = "sample_id"
        args.covar = ["C1", "C2", "C3", "Gender"]
        args.analysis_type = "cox"
        args.tte = "Time_To_Event"
        args.censure = "Censure"
        args.interaction = None
        args.chrx = False
        args.gender_column = "Gender"

        # The expected value
        expected_shape = (3, 6)
        expected_columns = {"C1", "C2", "C3", "Gender", "Time_To_Event",
                            "Censure"}
        expected_index = ["sample_1", "sample_2", "sample_3"]
        expected_c1 = np.array([0.3, 0.9, 0.4], dtype=float)
        expected_c2 = np.array([0.2, 0.1, 0.67], dtype=float)
        expected_c3 = np.array([0.45, 0.42, 999], dtype=float)
        expected_gender = np.array([1, 2, 1], dtype=int)
        expected_tte = np.array([10, 2, 8], dtype=int)
        expected_censure = np.array([0, 1, 1], dtype=int)
        expected_remove_g = False

        # The observed values
        observed_p, observed_remove_g = read_phenotype(filename, args)
        self.assertTrue(isinstance(observed_p, pd.DataFrame))
        self.assertEqual(expected_shape, observed_p.shape)
        self.assertEqual(expected_columns, set(observed_p.columns))
        self.assertEqual(expected_index, list(observed_p.index))
        self.assertTrue(np.allclose(expected_c1, observed_p.C1.values))
        self.assertTrue(np.allclose(expected_c2, observed_p.C2.values))
        self.assertTrue(np.allclose(expected_c3, observed_p.C3.values))
        self.assertTrue((expected_gender == observed_p.Gender.values).all())
        self.assertTrue(
            (expected_tte == observed_p.Time_To_Event.values).all()
        )
        self.assertTrue((expected_censure == observed_p.Censure.values).all())
        self.assertEqual(expected_remove_g, observed_remove_g)

        # Modifying the missing value to 999
        args.missing_value = "999"

        # The expected results
        expected_shape = (2, 6)

        # The observed values
        observed_p, observed_remove_g = read_phenotype(filename, args)
        self.assertTrue(isinstance(observed_p, pd.DataFrame))
        self.assertEqual(expected_shape, observed_p.shape)
        self.assertEqual(expected_columns, set(observed_p.columns))
        self.assertEqual(expected_index[:-1], list(observed_p.index))
        self.assertTrue(np.allclose(expected_c1[:-1], observed_p.C1.values))
        self.assertTrue(np.allclose(expected_c2[:-1], observed_p.C2.values))
        self.assertTrue(np.allclose(expected_c3[:-1], observed_p.C3.values))
        self.assertTrue(
            (expected_gender[:-1] == observed_p.Gender.values).all()
        )
        self.assertTrue(
            (expected_tte[:-1] == observed_p.Time_To_Event.values).all()
        )
        self.assertTrue(
            (expected_censure[:-1] == observed_p.Censure.values).all()
        )
        self.assertEqual(expected_remove_g, observed_remove_g)

        # Changing from Cox to linear should remove a column
        args.missing_value = None
        args.analysis_type = "linear"
        del args.tte
        del args.censure
        args.pheno_name = "Pheno_Lin"

        # The expected results
        expected_shape = (3, 5)
        expected_columns = {"C1", "C2", "C3", "Gender", "Pheno_Lin"}
        expected_pheno = np.array([0.01, 0.15, 0], dtype=float)

        # The observed values
        observed_p, observed_remove_g = read_phenotype(filename, args)
        self.assertTrue(isinstance(observed_p, pd.DataFrame))
        self.assertEqual(expected_shape, observed_p.shape)
        self.assertEqual(expected_columns, set(observed_p.columns))
        self.assertEqual(expected_index, list(observed_p.index))
        self.assertTrue(np.allclose(expected_c1, observed_p.C1.values))
        self.assertTrue(np.allclose(expected_c2, observed_p.C2.values))
        self.assertTrue(np.allclose(expected_c3, observed_p.C3.values))
        self.assertTrue((expected_gender == observed_p.Gender.values).all())
        self.assertTrue((expected_pheno == observed_p.Pheno_Lin.values).all())
        self.assertEqual(expected_remove_g, observed_remove_g)

        # Changing from linear to logistic shouldn't change a thing
        args.analysis_type = "logistic"
        args.pheno_name = "Pheno_Logit"

        # The expected results
        expected_columns = {"C1", "C2", "C3", "Gender", "Pheno_Logit"}
        expected_pheno = np.array([0, 1, 0], dtype=int)

        # The observed values
        observed_p, observed_remove_g = read_phenotype(filename, args)
        self.assertTrue(isinstance(observed_p, pd.DataFrame))
        self.assertEqual(expected_shape, observed_p.shape)
        self.assertEqual(expected_columns, set(observed_p.columns))
        self.assertEqual(expected_index, list(observed_p.index))
        self.assertTrue(np.allclose(expected_c1, observed_p.C1.values))
        self.assertTrue(np.allclose(expected_c2, observed_p.C2.values))
        self.assertTrue(np.allclose(expected_c3, observed_p.C3.values))
        self.assertTrue((expected_gender == observed_p.Gender.values).all())
        self.assertTrue(
            (expected_pheno == observed_p.Pheno_Logit.values).all()
        )
        self.assertEqual(expected_remove_g, observed_remove_g)

        # Adding an interaction
        args.interaction = "Inter"

        # The expected results
        expected_shape = (3, 6)
        expected_columns = {"C1", "C2", "C3", "Gender", "Pheno_Logit", "Inter"}
        expected_inter = np.array([0.00001, 0.00332, 0.000001], dtype=float)

        # The observed values
        observed_p, observed_remove_g = read_phenotype(filename, args)
        self.assertTrue(isinstance(observed_p, pd.DataFrame))
        self.assertEqual(expected_shape, observed_p.shape)
        self.assertEqual(expected_columns, set(observed_p.columns))
        self.assertEqual(expected_index, list(observed_p.index))
        self.assertTrue(np.allclose(expected_c1, observed_p.C1.values))
        self.assertTrue(np.allclose(expected_c2, observed_p.C2.values))
        self.assertTrue(np.allclose(expected_c3, observed_p.C3.values))
        self.assertTrue((expected_gender == observed_p.Gender.values).all())
        self.assertTrue(
            (expected_pheno == observed_p.Pheno_Logit.values).all()
        )
        self.assertTrue(np.allclose(expected_inter, observed_p.Inter.values))
        self.assertEqual(expected_remove_g, observed_remove_g)

        # Removing the gender in the covars, but setting chrx to true
        args.covar = ["C1", "C2", "C3"]
        args.chrx = True

        # The expected results
        expected_remove_g = True

        # The observed values
        observed_p, observed_remove_g = read_phenotype(filename, args)
        self.assertTrue(isinstance(observed_p, pd.DataFrame))
        self.assertEqual(expected_shape, observed_p.shape)
        self.assertEqual(expected_columns, set(observed_p.columns))
        self.assertEqual(expected_index, list(observed_p.index))
        self.assertTrue(np.allclose(expected_c1, observed_p.C1.values))
        self.assertTrue(np.allclose(expected_c2, observed_p.C2.values))
        self.assertTrue(np.allclose(expected_c3, observed_p.C3.values))
        self.assertTrue((expected_gender == observed_p.Gender.values).all())
        self.assertTrue(
            (expected_pheno == observed_p.Pheno_Logit.values).all()
        )
        self.assertTrue(np.allclose(expected_inter, observed_p.Inter.values))
        self.assertEqual(expected_remove_g, observed_remove_g)

        # Adding a sample (with unknown gender) (should be included since not
        # in covar, even though we ask for chrX)
        with open(filename, "a") as o_file:
            o_file.write(
                "sample_4\t8\t1\t0.4\t0.67\t999\t0.001\t0\t0.0\t0\t0.000001\n"
            )

        # The expected values
        expected_shape = (4, 6)
        expected_index.append("sample_4")
        expected_c1 = np.array([0.3, 0.9, 0.4, 0.4], dtype=float)
        expected_c2 = np.array([0.2, 0.1, 0.67, 0.67], dtype=float)
        expected_c3 = np.array([0.45, 0.42, 999, 999], dtype=float)
        expected_gender = np.array([1, 2, 1, 0], dtype=int)
        expected_pheno = np.array([0, 1, 0, 0], dtype=int)
        expected_inter = np.array([0.00001, 0.00332, 0.000001, 0.000001],
                                  dtype=float)

        # The observed values
        observed_p, observed_remove_g = read_phenotype(filename, args)
        self.assertTrue(isinstance(observed_p, pd.DataFrame))
        self.assertEqual(expected_shape, observed_p.shape)
        self.assertEqual(expected_columns, set(observed_p.columns))
        self.assertEqual(expected_index, list(observed_p.index))
        self.assertTrue(np.allclose(expected_c1, observed_p.C1.values))
        self.assertTrue(np.allclose(expected_c2, observed_p.C2.values))
        self.assertTrue(np.allclose(expected_c3, observed_p.C3.values))
        self.assertTrue((expected_gender == observed_p.Gender.values).all())
        self.assertTrue(
            (expected_pheno == observed_p.Pheno_Logit.values).all()
        )
        self.assertTrue(np.allclose(expected_inter, observed_p.Inter.values))
        self.assertEqual(expected_remove_g, observed_remove_g)

        # Sample shouldn't be included if chrx is False, but Gender in covars
        args.covar.append("Gender")
        args.chrx = False

        # The expected values
        expected_shape = (3, 6)
        expected_remove_g = False

        # The observed values
        observed_p, observed_remove_g = read_phenotype(filename, args)
        self.assertTrue(isinstance(observed_p, pd.DataFrame))
        self.assertEqual(expected_shape, observed_p.shape)
        self.assertEqual(expected_columns, set(observed_p.columns))
        self.assertEqual(expected_index[:-1], list(observed_p.index))
        self.assertTrue(np.allclose(expected_c1[:-1], observed_p.C1.values))
        self.assertTrue(np.allclose(expected_c2[:-1], observed_p.C2.values))
        self.assertTrue(np.allclose(expected_c3[:-1], observed_p.C3.values))
        self.assertTrue(
            (expected_gender[:-1] == observed_p.Gender.values).all()
        )
        self.assertTrue(
            (expected_pheno[:-1] == observed_p.Pheno_Logit.values).all()
        )
        self.assertTrue(
            np.allclose(expected_inter[:-1], observed_p.Inter.values)
        )
        self.assertEqual(expected_remove_g, observed_remove_g)

        # Removing gender in the covar should add a sample
        args.covar = args.covar[:-1]

        # The expected values
        expected_shape = (4, 5)
        expected_columns.remove("Gender")

        # The observed values
        observed_p, observed_remove_g = read_phenotype(filename, args)
        self.assertTrue(isinstance(observed_p, pd.DataFrame))
        self.assertEqual(expected_shape, observed_p.shape)
        self.assertEqual(expected_columns, set(observed_p.columns))
        self.assertEqual(expected_index, list(observed_p.index))
        self.assertTrue(np.allclose(expected_c1, observed_p.C1.values))
        self.assertTrue(np.allclose(expected_c2, observed_p.C2.values))
        self.assertTrue(np.allclose(expected_c3, observed_p.C3.values))
        self.assertTrue(
            (expected_pheno == observed_p.Pheno_Logit.values).all()
        )
        self.assertTrue(np.allclose(expected_inter, observed_p.Inter.values))
        self.assertEqual(expected_remove_g, observed_remove_g)

        # Setting chromosome to X should also include the sample
        args.chrx = True

        # The expected values
        expected_shape = (4, 6)
        expected_columns.add("Gender")
        expected_remove_g = True

        # The observed values
        observed_p, observed_remove_g = read_phenotype(filename, args)
        self.assertTrue(isinstance(observed_p, pd.DataFrame))
        self.assertEqual(expected_shape, observed_p.shape)
        self.assertEqual(expected_columns, set(observed_p.columns))
        self.assertEqual(expected_index, list(observed_p.index))
        self.assertTrue(np.allclose(expected_c1, observed_p.C1.values))
        self.assertTrue(np.allclose(expected_c2, observed_p.C2.values))
        self.assertTrue(np.allclose(expected_c3, observed_p.C3.values))
        self.assertTrue(
            (expected_pheno == observed_p.Pheno_Logit.values).all()
        )
        self.assertTrue(np.allclose(expected_inter, observed_p.Inter.values))
        self.assertEqual(expected_remove_g, observed_remove_g)

    def test_read_samples(self):
        """Tests the 'read_samples' function."""
        # Creating the sample file
        sample_content = (
            "ID_1 ID_2 missing father mother sex plink_pheno\n"
            "0 0 0 D D D B\n"
            "fam_1 sample_1 0 0 0 2 -9\n"
            "fam_1 sample_2 0 0 0 1 -9\n"
            "fam_2 sample_3 0 0 0 2 -9\n"
        )
        sample_filename = os.path.join(self.output_dir.name, "test.sample")
        with open(sample_filename, "w") as o_file:
            o_file.write(sample_content)

        # The expected values
        expected_columns = ["ID_1"]
        expected_index = ["sample_1", "sample_2", "sample_3"]
        expected_fam = ["fam_1", "fam_1", "fam_2"]

        # The observed values
        observed = read_samples(sample_filename)

        # Checking
        self.assertTrue(isinstance(observed, pd.DataFrame))
        self.assertEqual((3, 1), observed.shape)
        self.assertEqual(expected_columns, observed.columns)
        self.assertEqual(expected_index, list(observed.index.values))
        self.assertEqual(expected_fam, list(observed.ID_1.values))

        # Having a duplicated samples will trigger an exception
        sample_content = (
            "ID_1 ID_2 missing father mother sex plink_pheno\n"
            "0 0 0 D D D B\n"
            "fam_1 sample_1 0 0 0 2 -9\n"
            "fam_1 sample_2 0 0 0 1 -9\n"
            "fam_2 sample_2 0 0 0 2 -9\n"
        )
        with open(sample_filename, "w") as o_file:
            o_file.write(sample_content)

        # Checking
        with self.assertRaises(ValueError) as cm:
            read_samples(sample_filename)
        self.assertEqual("Index has duplicate keys: ['sample_2']",
                         str(cm.exception))

    def test_read_sites_to_extract(self):
        """Tests the 'test_read_sites_to_extract' function."""
        file_content = ["marker_{}".format(i) for i in range(100)] * 2
        filename = os.path.join(self.output_dir.name, "markers.txt")
        with open(filename, "w") as o_file:
            o_file.write("\n".join(file_content) + "\n")

        # The expected values
        expected = {"marker_{}".format(i) for i in range(100)}

        # The observed values
        observed = read_sites_to_extract(filename)

        # Checking
        self.assertEqual(expected, observed)

    @unittest.skip("Test not implemented")
    def test_compute_statistics(self):
        """Tests the 'compute_statistics' function."""
        self.fail("Test not implemented")

    @unittest.skip("Test not implemented")
    def test_process_impute2_site(self):
        """Tests the 'process_impute2_site' function."""
        self.fail("Test not implemented")

    def test_samples_with_hetero_calls(self):
        """Tests the 'samples_with_hetero_calls' function."""
        data = [
            ("sample_1", 1.0, 0.0, 0.0),
            ("sample_2", 0.0, 1.0, 0.0),
            ("sample_3", 0.0, 0.0, 1.0),
            ("sample_4", 0.9, 0.1, 0.0),
            ("sample_5", 0.1, 0.8, 0.1),
            ("sample_6", 0.0, 0.4, 0.6),
            ("sample_7", 0.2, 0.5, 0.3),
            ("sample_8", 0.9, 0.05, 0.05),
            ("sample_9", 0.0, 1.0, 0.0),
        ]
        data = pd.DataFrame(data, columns=["sample_id", "D1", "D2", "D3"])
        data = data.set_index("sample_id", verify_integrity=True)

        # The expected results
        expected = ["sample_2", "sample_5", "sample_7", "sample_9"]

        # The observed results
        observed = samples_with_hetero_calls(data, "D2")

        # Checking
        self.assertTrue(isinstance(observed, pd.Index))
        self.assertEqual(expected, list(observed))

    def test_get_formula(self):
        """Tests the 'get_formula' function."""
        # Testing with only one phenotype (no covars, no interaction)
        expected = "pheno ~ _GenoD"
        observed = get_formula("pheno", [], None)
        self.assertEqual(expected, observed)

        # Testing with one covar, no interaction
        expected = "pheno ~ _GenoD + C1"
        observed = get_formula("pheno", ["C1"], None)
        self.assertEqual(expected, observed)

        # Testing with more than one covar, no interaction
        expected = "pheno ~ _GenoD + C1 + C2 + C3"
        observed = get_formula("pheno", ["C1", "C2", "C3"], None)
        self.assertEqual(expected, observed)

        # Testing with without covar, but with interaction
        expected = "pheno ~ _GenoD + _GenoD*inter"
        observed = get_formula("pheno", [], "inter")
        self.assertEqual(expected, observed)

        # Testing with one covar and interaction
        expected = "pheno ~ _GenoD + inter + _GenoD*inter"
        observed = get_formula("pheno", ["inter"], "inter")
        self.assertEqual(expected, observed)

        # Testing with more than one covar and interaction
        expected = "pheno ~ _GenoD + C1 + C2 + C3 + inter + _GenoD*inter"
        observed = get_formula("pheno", ["C1", "C2", "C3", "inter"], "inter")
        self.assertEqual(expected, observed)

    @unittest.skip("Test not implemented")
    def test_fit_cox(self):
        """Tests the 'fit_cox' function."""
        self.fail("Test not implemented")

    @unittest.skip("Test not implemented")
    def test_fit_cox_interaction(self):
        """Tests the 'fit_cox' function."""
        self.fail("Test not implemented")

    def test_fit_linear(self):
        """Tests the 'fit_linear' function."""
        # Reading the data
        data_filename = resource_filename(
            __name__,
            "data/regression_sim.txt.bz2",
        )

        # This dataset contains 3 markers + 5 covariables
        data = pd.read_csv(data_filename, sep="\t", compression="bz2")

        # The formula for the first marker
        formula = "y ~ snp1 + C1 + C2 + C3 + age + gender"
        columns_to_keep = ["y", "snp1", "C1", "C2", "C3", "age", "gender"]

        # The expected results for the first marker (according to R)
        # The data was simulated so that snp1 had a coefficient of 0.1
        expected_coef = 0.09930262321654575
        expected_se = 0.00302135517743109
        expected_min_ci = 0.09337963040899197
        expected_max_ci = 0.10522561602409949
        expected_t = 32.866914806414108
        expected_p = 2.7965174627917724e-217

        # The observed results for the first marker
        observed = fit_linear(
            data=data[columns_to_keep].dropna(axis=0),
            formula=formula,
            result_col="snp1",
        )
        self.assertEqual(6, len(observed))
        observed_coef, observed_se, observed_min_ci, observed_max_ci, \
            observed_t, observed_p = observed

        # Comparing the results
        self.assertAlmostEqual(expected_coef, observed_coef, places=10)
        self.assertAlmostEqual(expected_se, observed_se, places=10)
        self.assertAlmostEqual(expected_min_ci, observed_min_ci, places=10)
        self.assertAlmostEqual(expected_max_ci, observed_max_ci, places=10)
        self.assertAlmostEqual(expected_t, observed_t, places=10)
        self.assertAlmostEqual(np.log10(expected_p), np.log10(observed_p),
                               places=10)

        # The formula for the second marker
        formula = "y ~ snp2 + C1 + C2 + C3 + age + gender"
        columns_to_keep = ["y", "snp2", "C1", "C2", "C3", "age", "gender"]

        # The expected results for the second marker (according to R)
        # The data was simulated so that snp1 had a coefficient of 0
        expected_coef = -0.00279702443754753
        expected_se = 0.00240385609310785
        expected_min_ci = -0.0075094867313642991
        expected_max_ci = 0.0019154378562692411
        expected_t = -1.1635573550209353
        expected_p = 0.24465167231462448

        # The observed results for the first marker
        observed = fit_linear(
            data=data[columns_to_keep].dropna(axis=0),
            formula=formula,
            result_col="snp2",
        )
        self.assertEqual(6, len(observed))
        observed_coef, observed_se, observed_min_ci, observed_max_ci, \
            observed_t, observed_p = observed

        # Comparing the results
        self.assertAlmostEqual(expected_coef, observed_coef, places=10)
        self.assertAlmostEqual(expected_se, observed_se, places=10)
        self.assertAlmostEqual(expected_min_ci, observed_min_ci, places=10)
        self.assertAlmostEqual(expected_max_ci, observed_max_ci, places=10)
        self.assertAlmostEqual(expected_t, observed_t, places=10)
        self.assertAlmostEqual(np.log10(expected_p), np.log10(observed_p),
                               places=10)

        # The formula for the third (and last) marker
        formula = "y ~ snp3 + C1 + C2 + C3 + age + gender"
        columns_to_keep = ["y", "snp3", "C1", "C2", "C3", "age", "gender"]

        # The expected results for the second marker (according to R)
        # The data was simulated so that snp1 had a coefficient of -0.12
        expected_coef = -0.11731595824657762
        expected_se = 0.00327175651867383
        expected_min_ci = -0.12372983188610413
        expected_max_ci = -0.1109020846070511
        expected_t = -35.857178728608552
        expected_p = 2.4882495142044017e-254

        # The observed results for the first marker
        observed = fit_linear(
            data=data[columns_to_keep].dropna(axis=0),
            formula=formula,
            result_col="snp3",
        )
        self.assertEqual(6, len(observed))
        observed_coef, observed_se, observed_min_ci, observed_max_ci, \
            observed_t, observed_p = observed

        # Comparing the results
        self.assertAlmostEqual(expected_coef, observed_coef, places=10)
        self.assertAlmostEqual(expected_se, observed_se, places=10)
        self.assertAlmostEqual(expected_min_ci, observed_min_ci, places=10)
        self.assertAlmostEqual(expected_max_ci, observed_max_ci, places=10)
        self.assertAlmostEqual(expected_t, observed_t, places=10)
        self.assertAlmostEqual(np.log10(expected_p), np.log10(observed_p),
                               places=10)

        # Asking for an invalid column should raise a KeyError
        with self.assertRaises(KeyError) as cm:
            fit_linear(
                data=data[columns_to_keep].dropna(axis=0),
                formula=formula,
                result_col="unknown",
            )

        with self.assertRaises(patsy.PatsyError) as cm:
            fit_linear(
                data=data[columns_to_keep].dropna(axis=0),
                formula=formula + " + unknown",
                result_col="snp4",
            )

    def test_fit_logistic(self):
        """Tests the 'fit_logistic' function."""
        # Reading the data
        data_filename = resource_filename(
            __name__,
            "data/regression_sim.txt.bz2",
        )

        # This dataset contains 3 markers + 5 covariables
        data = pd.read_csv(data_filename, sep="\t", compression="bz2")

        # The formula for the first marker
        formula = "y_d ~ snp1 + C1 + C2 + C3 + age + gender"
        columns_to_keep = ["y_d", "snp1", "C1", "C2", "C3", "age", "gender"]

        # The expected results for the first marker (according to R)
        expected_coef = -0.514309712761157334
        expected_se = 0.1148545370213162609
        expected_min_ci = -0.741288870474147710
        expected_max_ci = -0.290848443930784406
        expected_z = -4.477922475676383129
        expected_p = 7.53729612963228856e-06

        # The observed results for the first marker
        observed = fit_logistic(
            data=data[columns_to_keep].dropna(axis=0),
            formula=formula,
            result_col="snp1",
        )
        observed_coef, observed_se, observed_min_ci, observed_max_ci, \
            observed_z, observed_p, = observed

        # Comparing the results
        self.assertAlmostEqual(expected_coef, observed_coef, places=10)
        self.assertAlmostEqual(expected_se, observed_se, places=7)
        self.assertAlmostEqual(expected_min_ci, observed_min_ci, places=2)
        self.assertAlmostEqual(expected_max_ci, observed_max_ci, places=2)
        self.assertAlmostEqual(expected_z, observed_z, places=6)
        self.assertAlmostEqual(np.log10(expected_p), np.log10(observed_p),
                               places=5)

        # The formula for the second marker
        formula = "y_d ~ snp2 + C1 + C2 + C3 + age + gender"
        columns_to_keep = ["y_d", "snp2", "C1", "C2", "C3", "age", "gender"]

        # The expected results for the second marker (according to R)
        expected_coef = -0.0409615621727592721
        expected_se = 0.0898086129043482589
        expected_min_ci = -0.217201661656268197
        expected_max_ci = 0.135039323830941221
        expected_z = -0.456098372395372320
        expected_p = 6.48319240531225471e-01

        # The observed results for the first marker
        observed = fit_logistic(
            data=data[columns_to_keep].dropna(axis=0),
            formula=formula,
            result_col="snp2",
        )
        observed_coef, observed_se, observed_min_ci, observed_max_ci, \
            observed_z, observed_p, = observed

        # Comparing the results
        self.assertAlmostEqual(expected_coef, observed_coef, places=9)
        self.assertAlmostEqual(expected_se, observed_se, places=5)
        self.assertAlmostEqual(expected_min_ci, observed_min_ci, places=3)
        self.assertAlmostEqual(expected_max_ci, observed_max_ci, places=3)
        self.assertAlmostEqual(expected_z, observed_z, places=4)
        self.assertAlmostEqual(np.log10(expected_p), np.log10(observed_p),
                               places=5)

        # The formula for the third (and last) marker
        formula = "y_d ~ snp3 + C1 + C2 + C3 + age + gender"
        columns_to_keep = ["y_d", "snp3", "C1", "C2", "C3", "age", "gender"]

        # The expected results for the second marker (according to R)
        expected_coef = 0.6806154974808061864
        expected_se = 0.1216909125194588076
        expected_min_ci = 0.442504664626330035
        expected_max_ci = 0.919770526738653338
        expected_z = 5.5929854036715633825
        expected_p = 2.23198061422542684e-08

        # The observed results for the first marker
        observed = fit_logistic(
            data=data[columns_to_keep].dropna(axis=0),
            formula=formula,
            result_col="snp3",
        )
        observed_coef, observed_se, observed_min_ci, observed_max_ci, \
            observed_z, observed_p, = observed

        # Comparing the results
        self.assertAlmostEqual(expected_coef, observed_coef, places=10)
        self.assertAlmostEqual(expected_se, observed_se, places=7)
        self.assertAlmostEqual(expected_min_ci, observed_min_ci, places=3)
        self.assertAlmostEqual(expected_max_ci, observed_max_ci, places=2)
        self.assertAlmostEqual(expected_z, observed_z, places=5)
        self.assertAlmostEqual(np.log10(expected_p), np.log10(observed_p),
                               places=5)

        # Asking for an invalid column should raise a KeyError
        with self.assertRaises(KeyError) as cm:
            fit_logistic(
                data=data[columns_to_keep].dropna(axis=0),
                formula=formula,
                result_col="unknown",
            )

        with self.assertRaises(patsy.PatsyError) as cm:
            fit_logistic(
                data=data[columns_to_keep].dropna(axis=0),
                formula=formula + " + unknown",
                result_col="snp4",
            )

    def test_fit_linear_interaction(self):
        """Tests the 'fit_cox' function."""
        # Reading the data
        data_filename = resource_filename(
            __name__,
            "data/regression_sim_inter.txt.bz2",
        )

        # This dataset contains 3 markers + 5 covariables
        data = pd.read_csv(data_filename, sep="\t", compression="bz2")

        # The formula for the first marker
        formula = "y ~ snp1 + C1 + C2 + C3 + age + gender + snp1*gender"
        columns_to_keep = ["y", "snp1", "C1", "C2", "C3", "age", "gender"]

        # The expected results for the first marker (according to R)
        # The data was simulated so that snp1 had a coefficient of 0.1
        expected_coef = 0.101959570845217173
        expected_se = 0.00588764130382715949
        expected_min_ci = 0.090417578486636035
        expected_max_ci = 0.11350156320379831
        expected_t = 17.3175581839437314
        expected_p = 1.5527088106478929e-65

        # The observed results
        observed = fit_linear(
            data=data[columns_to_keep].dropna(axis=0),
            formula=formula,
            result_col="snp1:gender",
        )
        self.assertEqual(6, len(observed))
        observed_coef, observed_se, observed_min_ci, observed_max_ci, \
            observed_t, observed_p = observed

        # Comparing the results
        self.assertAlmostEqual(expected_coef, observed_coef, places=10)
        self.assertAlmostEqual(expected_se, observed_se, places=10)
        self.assertAlmostEqual(expected_min_ci, observed_min_ci, places=10)
        self.assertAlmostEqual(expected_max_ci, observed_max_ci, places=10)
        self.assertAlmostEqual(expected_t, observed_t, places=10)
        self.assertAlmostEqual(np.log10(expected_p), np.log10(observed_p),
                               places=10)

    def test_fit_logistic_interaction(self):
        """Tests the 'fit_cox' function."""
        # Reading the data
        data_filename = resource_filename(
            __name__,
            "data/regression_sim_inter.txt.bz2",
        )

        # This dataset contains 3 markers + 5 covariables
        data = pd.read_csv(data_filename, sep="\t", compression="bz2")

        # The formula for the first marker
        formula = "y_d ~ snp1 + C1 + C2 + C3 + age + gender + snp1*gender"
        columns_to_keep = ["y_d", "snp1", "C1", "C2", "C3", "age", "gender"]

        # The expected results for the first marker (according to R)
        expected_coef = -0.4998229445983128905
        expected_se = 0.2425924038476814093
        expected_min_ci = -0.9779101205637230620
        expected_max_ci = -0.0263169240328645603
        expected_z = -2.0603404586078508665
        expected_p = 3.93660046768015970e-02

        # The observed results
        observed = fit_logistic(
            data=data[columns_to_keep],
            formula=formula,
            result_col="snp1:gender",
        )
        self.assertEqual(6, len(observed))
        observed_coef, observed_se, observed_min_ci, observed_max_ci, \
            observed_z, observed_p = observed

        # Comparing the results
        self.assertAlmostEqual(expected_coef, observed_coef, places=10)
        self.assertAlmostEqual(expected_se, observed_se, places=7)
        self.assertAlmostEqual(expected_min_ci, observed_min_ci, places=2)
        self.assertAlmostEqual(expected_max_ci, observed_max_ci, places=2)
        self.assertAlmostEqual(expected_z, observed_z, places=6)
        self.assertAlmostEqual(np.log10(expected_p), np.log10(observed_p),
                               places=6)

    def test_full_fit_linear(self):
        """Tests the full pipeline for linear regression."""
        # Reading the data
        data_filename = resource_filename(
            __name__,
            "data/regression_sim.txt.bz2",
        )

        # Creating the input files
        o_prefix, options = create_input_files(
            i_filename=data_filename,
            output_dirname=self.output_dir.name,
            analysis_type="linear",
        )

        # Executing the tool
        main(args=options)

        # Cleaning the handlers
        TestImputedStats.clean_logging_handlers()

        # Making sure the output file exists
        self.assertTrue(os.path.isfile(o_prefix + ".linear.dosage"))

        # Reading the data
        observed = pd.read_csv(o_prefix + ".linear.dosage", sep="\t")

        # Checking all columns are present
        self.assertEqual(["chr", "pos", "snp", "major", "minor", "maf", "n",
                          "coef", "se", "lower", "upper", "t", "p"],
                         list(observed.columns))

        # Chromosomes
        self.assertEqual([22], observed.chr.unique())

        # Positions
        self.assertEqual([1, 2, 3], list(observed.pos))

        # Marker names
        self.assertEqual(["marker_1", "marker_2", "marker_3"],
                         list(observed.snp))

        # Major alleles
        self.assertEqual(["T", "G", "AT"], list(observed.major))

        # Minor alleles
        self.assertEqual(["C", "A", "A"], list(observed.minor))

        # Minor allele frequency
        expected = [1724 / 11526, 4604 / 11526, 1379 / 11526]
        for expected_maf, observed_maf in zip(expected, observed.maf):
            self.assertAlmostEqual(expected_maf, observed_maf, places=10)

        # The number of samples
        expected = [5763, 5763, 5763]
        for expected_n, observed_n in zip(expected, observed.n):
            self.assertEqual(expected_n, observed_n)

        # The coefficients
        expected = [0.09930262321654575, -0.00279702443754753,
                    -0.11731595824657762]
        for expected_coef, observed_coef in zip(expected, observed.coef):
            self.assertAlmostEqual(expected_coef, observed_coef, places=10)

        # The standard error
        expected = [0.00302135517743109, 0.00240385609310785,
                    0.00327175651867383]
        for expected_se, observed_se in zip(expected, observed.se):
            self.assertAlmostEqual(expected_se, observed_se, places=10)

        # The lower CI
        expected = [0.09337963040899197, -0.0075094867313642991,
                    -0.12372983188610413]
        for expected_min_ci, observed_min_ci in zip(expected, observed.lower):
            self.assertAlmostEqual(expected_min_ci, observed_min_ci, places=10)

        # The upper CI
        expected = [0.10522561602409949, 0.0019154378562692411,
                    -0.1109020846070511]
        for expected_max_ci, observed_max_ci in zip(expected, observed.upper):
            self.assertAlmostEqual(expected_max_ci, observed_max_ci, places=10)

        # The T statistics
        expected = [32.866914806414108, -1.1635573550209353,
                    -35.857178728608552]
        for expected_t, observed_t in zip(expected, observed.t):
            self.assertAlmostEqual(expected_t, observed_t, places=10)

        # The p values
        expected = [2.7965174627917724e-217, 0.24465167231462448,
                    2.4882495142044017e-254]
        for expected_p, observed_p in zip(expected, observed.p):
            self.assertAlmostEqual(np.log10(expected_p), np.log10(observed_p),
                                   places=10)

    def test_full_fit_logistic(self):
        """Tests the full pipeline for logistic regression."""
        # Reading the data
        data_filename = resource_filename(
            __name__,
            "data/regression_sim.txt.bz2",
        )

        # Creating the input files
        o_prefix, options = create_input_files(
            i_filename=data_filename,
            output_dirname=self.output_dir.name,
            analysis_type="logistic",
            pheno_name="y_d",
        )

        # Executing the tool
        main(args=options)

        # Cleaning the handlers
        TestImputedStats.clean_logging_handlers()

        # Making sure the output file exists
        self.assertTrue(os.path.isfile(o_prefix + ".logistic.dosage"))

        # Reading the data
        observed = pd.read_csv(o_prefix + ".logistic.dosage", sep="\t")

        # Checking all columns are present
        self.assertEqual(["chr", "pos", "snp", "major", "minor", "maf", "n",
                          "coef", "se", "lower", "upper", "z", "p"],
                         list(observed.columns))

        # Chromosomes
        self.assertEqual([22], observed.chr.unique())

        # Positions
        self.assertEqual([1, 2, 3], list(observed.pos))

        # Marker names
        self.assertEqual(["marker_1", "marker_2", "marker_3"],
                         list(observed.snp))

        # Major alleles
        self.assertEqual(["T", "G", "AT"], list(observed.major))

        # Minor alleles
        self.assertEqual(["C", "A", "A"], list(observed.minor))

        # Minor allele frequency
        expected = [1778 / 11880, 4703 / 11760, 1427 / 11880]
        for expected_maf, observed_maf in zip(expected, observed.maf):
            self.assertAlmostEqual(expected_maf, observed_maf, places=10)

        # The number of samples
        expected = [5940, 5880, 5940]
        for expected_n, observed_n in zip(expected, observed.n):
            self.assertEqual(expected_n, observed_n)

        # The coefficients
        expected = [-0.514309712761163662, -0.0409615621727604101,
                    0.6806154974808032998]
        places = [10, 9, 10]
        zipped = zip(expected, observed.coef, places)
        for expected_coef, observed_coef, place in zipped:
            self.assertAlmostEqual(expected_coef, observed_coef, places=place)

        # The standard error
        expected = [0.1148545370213169270, 0.0898086129043478426,
                    0.1216909125194589325]
        places = [7, 5, 7]
        zipped = zip(expected, observed.se, places)
        for expected_se, observed_se, place in zipped:
            self.assertAlmostEqual(expected_se, observed_se, places=place)

        # The lower CI
        expected = [-0.741288870474143935, -0.217201661656271972,
                    0.442504664626339528]
        places = [2, 3, 3]
        zipped = zip(expected, observed.lower, places)
        for expected_min_ci, observed_min_ci, place in zipped:
            self.assertAlmostEqual(expected_min_ci, observed_min_ci,
                                   places=place)

        # The upper CI
        expected = [-0.290848443930769640, 0.135039323830934560,
                    0.919770526738648897]
        places = [2, 3, 2]
        zipped = zip(expected, observed.upper, places)
        for expected_max_ci, observed_max_ci, place in zipped:
            self.assertAlmostEqual(expected_max_ci, observed_max_ci,
                                   places=place)

        # The Z statistics
        expected = [-4.477922475676412439, -0.456098372395387086,
                    5.592985403671533184]
        places = [6, 4, 5]
        zipped = zip(expected, observed.z, places)
        for expected_z, observed_z, place in zipped:
            self.assertAlmostEqual(expected_z, observed_z, places=place)

        # The p values
        expected = [7.53729612963125518e-06, 6.48319240531214813e-01,
                    2.23198061422581463e-08]
        places = [5, 5, 5]
        zipped = zip(expected, observed.p, places)
        for expected_p, observed_p, place in zipped:
            self.assertAlmostEqual(np.log10(expected_p), np.log10(observed_p),
                                   places=place)

    def test_full_fit_linear_multiprocess(self):
        """Tests the full pipeline for linear regression."""
        # Reading the data
        data_filename = resource_filename(
            __name__,
            "data/regression_sim.txt.bz2",
        )

        # Creating the input files
        o_prefix, options = create_input_files(
            i_filename=data_filename,
            output_dirname=self.output_dir.name,
            analysis_type="linear",
            nb_process=2,
        )

        # Executing the tool
        main(args=options)

        # Cleaning the handlers
        TestImputedStats.clean_logging_handlers()

        # Making sure the output file exists
        self.assertTrue(os.path.isfile(o_prefix + ".linear.dosage"))

        # Reading the data
        observed = pd.read_csv(o_prefix + ".linear.dosage", sep="\t")

        # Checking all columns are present
        self.assertEqual(["chr", "pos", "snp", "major", "minor", "maf", "n",
                          "coef", "se", "lower", "upper", "t", "p"],
                         list(observed.columns))

        # Chromosomes
        self.assertEqual([22], observed.chr.unique())

        # Positions
        self.assertEqual([1, 2, 3], list(observed.pos))

        # Marker names
        self.assertEqual(["marker_1", "marker_2", "marker_3"],
                         list(observed.snp))

        # Major alleles
        self.assertEqual(["T", "G", "AT"], list(observed.major))

        # Minor alleles
        self.assertEqual(["C", "A", "A"], list(observed.minor))

        # Minor allele frequency
        expected = [1724 / 11526, 4604 / 11526, 1379 / 11526]
        for expected_maf, observed_maf in zip(expected, observed.maf):
            self.assertAlmostEqual(expected_maf, observed_maf, places=10)

        # The number of samples
        expected = [5763, 5763, 5763]
        for expected_n, observed_n in zip(expected, observed.n):
            self.assertEqual(expected_n, observed_n)

        # The coefficients
        expected = [0.09930262321654575, -0.00279702443754753,
                    -0.11731595824657762]
        for expected_coef, observed_coef in zip(expected, observed.coef):
            self.assertAlmostEqual(expected_coef, observed_coef, places=10)

        # The standard error
        expected = [0.00302135517743109, 0.00240385609310785,
                    0.00327175651867383]
        for expected_se, observed_se in zip(expected, observed.se):
            self.assertAlmostEqual(expected_se, observed_se, places=10)

        # The lower CI
        expected = [0.09337963040899197, -0.0075094867313642991,
                    -0.12372983188610413]
        for expected_min_ci, observed_min_ci in zip(expected, observed.lower):
            self.assertAlmostEqual(expected_min_ci, observed_min_ci, places=10)

        # The upper CI
        expected = [0.10522561602409949, 0.0019154378562692411,
                    -0.1109020846070511]
        for expected_max_ci, observed_max_ci in zip(expected, observed.upper):
            self.assertAlmostEqual(expected_max_ci, observed_max_ci, places=10)

        # The T statistics
        expected = [32.866914806414108, -1.1635573550209353,
                    -35.857178728608552]
        for expected_t, observed_t in zip(expected, observed.t):
            self.assertAlmostEqual(expected_t, observed_t, places=10)

        # The p values
        expected = [2.7965174627917724e-217, 0.24465167231462448,
                    2.4882495142044017e-254]
        for expected_p, observed_p in zip(expected, observed.p):
            self.assertAlmostEqual(np.log10(expected_p), np.log10(observed_p),
                                   places=10)

    def test_full_fit_logistic_multiprocess(self):
        """Tests the full pipeline for logistic regression."""
        # Reading the data
        data_filename = resource_filename(
            __name__,
            "data/regression_sim.txt.bz2",
        )

        # Creating the input files
        o_prefix, options = create_input_files(
            i_filename=data_filename,
            output_dirname=self.output_dir.name,
            analysis_type="logistic",
            pheno_name="y_d",
            nb_process=2,
        )

        # Executing the tool
        main(args=options)

        # Cleaning the handlers
        TestImputedStats.clean_logging_handlers()

        # Making sure the output file exists
        self.assertTrue(os.path.isfile(o_prefix + ".logistic.dosage"))

        # Reading the data
        observed = pd.read_csv(o_prefix + ".logistic.dosage", sep="\t")

        # Checking all columns are present
        self.assertEqual(["chr", "pos", "snp", "major", "minor", "maf", "n",
                          "coef", "se", "lower", "upper", "z", "p"],
                         list(observed.columns))

        # Chromosomes
        self.assertEqual([22], observed.chr.unique())

        # Positions
        self.assertEqual([1, 2, 3], list(observed.pos))

        # Marker names
        self.assertEqual(["marker_1", "marker_2", "marker_3"],
                         list(observed.snp))

        # Major alleles
        self.assertEqual(["T", "G", "AT"], list(observed.major))

        # Minor alleles
        self.assertEqual(["C", "A", "A"], list(observed.minor))

        # Minor allele frequency
        expected = [1778 / 11880, 4703 / 11760, 1427 / 11880]
        for expected_maf, observed_maf in zip(expected, observed.maf):
            self.assertAlmostEqual(expected_maf, observed_maf, places=10)

        # The number of samples
        expected = [5940, 5880, 5940]
        for expected_n, observed_n in zip(expected, observed.n):
            self.assertEqual(expected_n, observed_n)

        # The coefficients
        expected = [-0.514309712761163662, -0.0409615621727604101,
                    0.6806154974808032998]
        places = [10, 9, 10]
        zipped = zip(expected, observed.coef, places)
        for expected_coef, observed_coef, place in zipped:
            self.assertAlmostEqual(expected_coef, observed_coef, places=place)

        # The standard error
        expected = [0.1148545370213169270, 0.0898086129043478426,
                    0.1216909125194589325]
        places = [7, 5, 7]
        zipped = zip(expected, observed.se, places)
        for expected_se, observed_se, place in zipped:
            self.assertAlmostEqual(expected_se, observed_se, places=place)

        # The lower CI
        expected = [-0.741288870474143935, -0.217201661656271972,
                    0.442504664626339528]
        places = [2, 3, 3]
        zipped = zip(expected, observed.lower, places)
        for expected_min_ci, observed_min_ci, place in zipped:
            self.assertAlmostEqual(expected_min_ci, observed_min_ci,
                                   places=place)

        # The upper CI
        expected = [-0.290848443930769640, 0.135039323830934560,
                    0.919770526738648897]
        places = [2, 3, 2]
        zipped = zip(expected, observed.upper, places)
        for expected_max_ci, observed_max_ci, place in zipped:
            self.assertAlmostEqual(expected_max_ci, observed_max_ci,
                                   places=place)

        # The Z statistics
        expected = [-4.477922475676412439, -0.456098372395387086,
                    5.592985403671533184]
        places = [6, 4, 5]
        zipped = zip(expected, observed.z, places)
        for expected_z, observed_z, place in zipped:
            self.assertAlmostEqual(expected_z, observed_z, places=place)

        # The p values
        expected = [7.53729612963125518e-06, 6.48319240531214813e-01,
                    2.23198061422581463e-08]
        places = [5, 5, 5]
        zipped = zip(expected, observed.p, places)
        for expected_p, observed_p, place in zipped:
            self.assertAlmostEqual(np.log10(expected_p), np.log10(observed_p),
                                   places=place)

    def test_full_fit_linear_interaction(self):
        """Tests the full pipeline for linear regression."""
        # Reading the data
        data_filename = resource_filename(
            __name__,
            "data/regression_sim_inter.txt.bz2",
        )

        # Creating the input files
        o_prefix, options = create_input_files(
            i_filename=data_filename,
            output_dirname=self.output_dir.name,
            analysis_type="linear",
            interaction="gender",
        )

        # Executing the tool
        main(args=options)

        # Cleaning the handlers
        TestImputedStats.clean_logging_handlers()

        # Making sure the output file exists
        self.assertTrue(os.path.isfile(o_prefix + ".linear.dosage"))

        # Reading the data
        observed = pd.read_csv(o_prefix + ".linear.dosage", sep="\t")

        # Checking all columns are present
        self.assertEqual(["chr", "pos", "snp", "major", "minor", "maf", "n",
                          "coef", "se", "lower", "upper", "t", "p"],
                         list(observed.columns))

        # Chromosomes
        self.assertEqual([22], observed.chr.unique())

        # Positions
        self.assertEqual([1, 2, 3], list(observed.pos))

        # Marker names
        self.assertEqual(["marker_1", "marker_2", "marker_3"],
                         list(observed.snp))

        # Major alleles
        self.assertEqual(["T", "G", "AT"], list(observed.major))

        # Minor alleles
        self.assertEqual(["C", "A", "A"], list(observed.minor))

        # Minor allele frequency
        expected = [1724 / 11526, 4604 / 11526, 1379 / 11526]
        for expected_maf, observed_maf in zip(expected, observed.maf):
            self.assertAlmostEqual(expected_maf, observed_maf, places=10)

        # The number of samples
        expected = [5763, 5763, 5763]
        for expected_n, observed_n in zip(expected, observed.n):
            self.assertEqual(expected_n, observed_n)

        # The coefficients
        expected = [0.1019595708452171734, -0.010917110807672320352,
                    0.02657634353683377762]
        for expected_coef, observed_coef in zip(expected, observed.coef):
            self.assertAlmostEqual(expected_coef, observed_coef, places=10)

        # The standard error
        expected = [0.005887641303827159493, 0.006578361146066042525,
                    0.009435607764482155033]
        for expected_se, observed_se in zip(expected, observed.se):
            self.assertAlmostEqual(expected_se, observed_se, places=10)

        # The lower CI
        expected = [0.0904175784866360355, -0.0238131739612693419,
                    0.00807900188569928013]
        for expected_min_ci, observed_min_ci in zip(expected, observed.lower):
            self.assertAlmostEqual(expected_min_ci, observed_min_ci, places=10)

        # The upper CI
        expected = [0.113501563203798311, 0.00197895234592469944,
                    0.0450736851879682751]
        for expected_max_ci, observed_max_ci in zip(expected, observed.upper):
            self.assertAlmostEqual(expected_max_ci, observed_max_ci, places=10)

        # The T statistics
        expected = [17.31755818394373136, -1.65954871817898208519,
                    2.816601134785761129]
        for expected_t, observed_t in zip(expected, observed.t):
            self.assertAlmostEqual(expected_t, observed_t, places=10)

        # The p values
        expected = [1.55270881064789290e-65, 9.70597574168038796e-02,
                    4.87000487450673421e-03]
        for expected_p, observed_p in zip(expected, observed.p):
            self.assertAlmostEqual(np.log10(expected_p), np.log10(observed_p),
                                   places=10)

    @unittest.skip("Test not implemented")
    def test_fit_interaction(self):
        """Tests the 'fit_logistic' function."""
        self.fail("Test not implemented")

    @unittest.skip("Test not implemented")
    def test_get_result_from_linear_logistic(self):
        """Tests the '_get_result_from_linear_logistic' function."""
        self.fail("Test not implemented")

    @unittest.skip("Test not implemented")
    def test_check_args(self):
        """Tests the 'check_args' function."""
        self.fail("Test not implemented")
