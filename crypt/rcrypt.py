"""
The rcrypt module implements various cryptographic functions that are required by 
the Helium cryptocurrency application
This module requires the pycryptodome package to be installed. 
The base58 package encodes strings into base58 format.
This module uses Python's regular expression module re.
This module uses the secrets module in the Python standard library to generate
cryptographically secure hexadecimal encoded strings.
"""
# import the regular expressions module
import re
# imports from the cryptodome package
from Crypto.Hash import SHA3_256
from Crypto.PublicKey import ECC
from Crypto.PublicKey import DSA
from Crypto.Signature import DSS
from Crypto.Hash import SHA256
from Crypto.Hash import RIPEMD160

import base58
import secrets

# import Python's debugging and logging modules
import pdb
import logging

"""
   log debugging messages to the file debug.log
"""
logging.basicConfig(filename="debug.log",filemode="w", format='%(asctime)s:%(levelname)s:%(message)s', 
    level=logging.DEBUG)


def make_SHA256_hash(msg: 'string') -> 'string':
    """
    make_sha256_hash computes the SHA-256 message digest or cryptographic hash 
    for a received string argument. The secure hash value that is generated is converted
    into a sequence of hexadecimal digits and then returned by the function.
    The hexadecimal format of the message digest is 64 bytes long.
    """
    #convert the received msg string to a sequence of ascii bytes
    message = bytes(msg, 'ascii')

    # compute the SHA-256 message digest of msg and convert to a hexadecimal format
    hash_object = SHA256.new()
    hash_object.update(message)
    return hash_object.hexdigest()


def validate_SHA256_hash(digest: "string") -> bool:
    """
    validate_SHA256_hash: tests whether a string has an encoding conforming to a
    SHA-256 message digest in hexadecimal string format (64 bytes).
    """
    # a hexadecimal SHA256 message digest must be 64 bytes long.
    if len(digest) != 64: return False
    
    # This regular expression tests that the received string contains only 
    # hexadecimal characters    
    if re.search('[^0-9a-fA-F]', digest) == None: return True
    return False
     


def make_RIPEMD160_hash(message: 'byte stream') -> 'string':
    """
    RIPEMD-160 is a cryptographic algorithm that emits a 20 byte message digest.
    This function computes the RIPEMD-160 message digest of a message and returns
    the hexadecimal string encoded representation of the message digest (40 bytes).
    """
    # convert message to an ascii byte stream
    bstr = bytes(message, 'ascii')
    # generate the RIPEMD hash of message
    h = RIPEMD160.new()
    h.update(bstr)
    # convert to a hexadecimal encoded string
    hash = h.hexdigest()
    return hash


def validate_RIPEMD160_hash(digest: 'string') -> 'bool':
    """
    tests that a received string has an encoding conforming to a RIPE160 hash in 
    hexadecimal format
    """
    if len(digest) != 40: return False
    
    # This regular expression tests that received string only contains 
    # hexadecimal characters    
    if re.search('[^0-9a-fA-F]+', digest) == None: return True

    return False


def make_ecc_keys():
    """
    make a private-public key pair using the elliptic curve cryptographic  
    functions in the pyCryptodome package. 
    returns a tuple with the private key and public key in PEM format
    """
    # generate an ecc object
    ecc_key = ECC.generate(curve='P-256')
    # get the public key object
    pk_object = ecc_key.public_key()
    # export the private-public key pair in PEM format
    p = (ecc_key.export_key(format='PEM'), pk_object.export_key(format='PEM'))

    return p


def sign_message(private_key: 'String', message: 'String') -> 'string':
    """
    digitally signs a message using a private key generated using the
    elliptic cryptography module of the pyCryptodome package. 
    Receives a private key in PEM format and the message that is to be
    digitally signed.
    returns a hex encoded signature string.
    """
    # import the PEM format private key
    priv_key = ECC.import_key(private_key)

    # convert the message to a byte stream and 
    # compute the SHA-256 message digest of the message
    bstr = bytes(message, 'ascii')

    hash   = SHA256.new(bstr)
    # create a digital signature object from the private key
    signer = DSS.new(priv_key, 'fips-186-3')

    # sign the SHA-256 message digest. 
    signature = signer.sign(hash)
    sig = signature.hex()
    return sig


def verify_signature(public_key: 'String', msg: 'String', signature: 'string') -> 'bool':
    """
    tests whether a message is digitally signed by a private key to which a
    public key is paired.
    Receives a ECC public key in PEM format, the message that is to to be verified 
    and the digital signature of the message.
    Returns True or False
    """
    try: 
         # convert the message to a byte stream and compute the SHA-256 hash
         msg = bytes(msg, 'ascii')
         msg_hash = SHA256.new(msg)
     
         # signature to bytes
         signature = bytes.fromhex(signature)
         # import the PEM formatted public key and create a signature verifier
         # object from the public key
         pub_key  = ECC.import_key(public_key)
         verifier = DSS.new(pub_key, 'fips-186-3')

         # Verify the authenticity of the signed message
         verifier.verify(msg_hash, signature)
         return True

    except Exception as err:
        logging.debug('verify_signature: exception: ' + str(err))



def make_address(prefix: 'string') -> 'string':
    """
    generates a Helium address from a ECC public key in PEM format. 
    prefix is a single numeric character which describes the type of
    the address. This prefix must be '1'
    """
    
    key = ECC.generate(curve='P-256')
    __private_key = key.export_key(format='PEM')
    public_key = key.public_key().export_key(format='PEM')

    val = make_SHA256_hash(public_key)
    val = make_RIPEMD160_hash(val)
    tmp = prefix + val

    # make a checksum
    checksum = make_SHA256_hash(tmp)
    checksum = checksum[len(checksum) - 4:]
  
    # add the checksum to the tmp result
    address = tmp + checksum

    # encode addr as a base58 sequence of bytes
    address =  base58.b58encode(address.encode())

    # The decode function converts a byte sequence to a string
    address = address.decode("ascii")

    return address


def validate_address(address: 'string') -> bool: 
    """
     validates a Helium address using the four character checksum appended
     to the address. Receives a base58 encoded address.
     """
    
    # encode the string address as a sequence of bytes
    addr = address.encode("ascii")
    # reverse the base58 encoding of the address
    addr = base58.b58decode(addr)
    # convert the address into a string
    addr = addr.decode("ascii") 

    # length must be RIPEMD-160 hash length + length of checksum + 1
    if (len(addr) != 45): return False
    if (addr[0] != '1'):  return False 

    # extract the checksum 
    extracted_checksum = addr[len(addr) - 4:]

    # extract the checksum out of addr and compute the
    # SHA-256 hash of the remaining addr string
    tmp = addr[:len(addr)- 4]
    tmp = make_SHA256_hash(tmp) 

    # get the computed checksum from tmp 
    checksum = tmp[len(tmp) - 4:]

    if extracted_checksum  == checksum: return True
    
    return False


def make_uuid() -> 'string':
    """
    makes an univerally unique 256 bit id encoded as a hexadecimal string that is
    used as a transaction identifier. Uses the Python standard library secrets module to
    generate a cryptographically strong random 32 byte string encoded as a hexadecimal 
    string (64 bytes)
    """
    id = secrets.token_hex(32)

    return id

