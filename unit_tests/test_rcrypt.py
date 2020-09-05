"""
pytest unit tests for the rcrypt module 
"""
import pytest
import rcrypt
import pdb

@pytest.mark.parametrize("input_string, value", [
    ('hello world', True),
    ('the quick brown fox jumped over the sleeping dog', True),
    ('0', True),
    ('', True)
])
def test_make_SHA256_hash(input_string, value):
    """
    test that a SHA-256 message digest is created
    """
    ret = rcrypt.make_SHA256_hash(input_string)
    assert rcrypt.validate_SHA256_hash(ret) == value


@pytest.mark.parametrize("input_string, value", [
    ('a silent night and a pale paper moon over the saskatchewan river', 64),
    ('Farmer Brown and the sheep-dog', 64),
    ('', 64)
])
def test_SHA256_hash_length(input_string, value):
    """
    test that the length of created SHA3-256 hash in hexadecimal format is
    is 64 bytes
    """
    assert len(rcrypt.make_SHA256_hash('hello world')) == 64


@pytest.mark.parametrize("digest, value", [    
    ("123", False),
    ("644bcc7e564373040999aac89e7622f3ca71fba1d972fd94a31c3bfbf24e3938", True),
    ("644bcc7e564373040999aac89e7622f3ca71fba1d972fd94a31c3bfbf24e39380", False),
    ("644bcc7e564373040999aac89e7622f3ca71fba1d972fd94a31cZbfbf24e3938", False),
    ('', False),
    ("644bcc7e564373040999aac89e7622f3caz1fba1d972fd94a31c3bfbf24e3938", False),
])
def test_validate_SHA256_hash(digest, value):
    """
    validate whether a valid SHA-256 message digest format is generated
    """
    assert rcrypt.validate_SHA256_hash(digest) == value


@pytest.mark.parametrize("string_input, value", [
    ("0", True),
    ('andromeda galaxy', True),
    ('Farmer Brown and the sheep-dog', True),
    ('0', True)
])
def test_make_RIPEMD160_hash(string_input, value):
    """
    validate that a valid RIPEMD-160 message digest format is generated
    """
    ret = rcrypt.make_RIPEMD160_hash(string_input)
    assert rcrypt.validate_RIPEMD160_hash(ret) == value


@pytest.mark.parametrize("hash, value", [
    ('123456789098765432169Q156c79FFa1200CCB1A', False),
    ("lkorkflfor4flgofmr", False),
    ('off0099ijf87', False),
    ('1234567890A87654321690156c79FFa1200CCB1A', True),
])
def test_validate_RIPEMD160_hash(hash, value):
    """
    validate whether a string is in RIPEMD-160 message digest format
    """
    assert rcrypt.validate_RIPEMD160_hash(hash) == value


def test_make_ecc_keys():
    """
    test ECC private-public key pair
    """
    ecc_keys = rcrypt.make_ecc_keys()
    assert ecc_keys[0].find("BEGIN PRIVATE KEY") >= 0
    assert ecc_keys[0].find("END PRIVATE KEY") >= 0
    assert ecc_keys[0].find("END PRIVATE KEY") > ecc_keys[0].find("BEGIN PRIVATE KEY") 
    assert ecc_keys[1].find("BEGIN PUBLIC KEY") >= 0
    assert ecc_keys[1].find("END PUBLIC KEY") >= 0
    assert ecc_keys[1].find("END PUBLIC KEY") > ecc_keys[1].find("BEGIN PUBLIC KEY") 


@pytest.mark.parametrize("message, value", [
    ('50bfee49c706d766411777aac1c9f35456c33ecea2afb4f3c8f1033b0298bdc9', True),
    ('6e6404d8693aea119a8ef7cf82c56fe96555d8df2c36c2b9e325411fbef62014', True),
    ('ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad', True),
    ('hello world', True),
])
def test_sign_message(message, value):
    """
    Digitally sign a message and then verify it
    """
    ecc_tuple = rcrypt.make_ecc_keys()
    priv_key  = ecc_tuple[0]
    pub_key   = ecc_tuple[1]
    
    sig = rcrypt.sign_message(priv_key, message)
    
    ret = rcrypt.verify_signature(pub_key, message, sig)
    assert ret == value



@pytest.mark.parametrize("prefix, value", [
    ("a", False),
    ("1", True),
    ("Q", False),
    ("qwerty", False),
    ("", False),
])
def test_make_address(prefix, value):
    """
    test the generation of Helium addresses from seeds
    """
    ret = rcrypt.make_address(prefix)
    assert rcrypt.validate_address(ret) == value



@pytest.mark.parametrize("length, ret", [
    (64, True),
    (32, False)
])
def test_make_uuid(length, ret):
    """
    test id generation
    """
    id = rcrypt.make_uuid()
    assert (len(id) == length) == ret

