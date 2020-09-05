from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Hash import SHA256
from Crypto import Random
from hashlib import sha256
import binascii


#=====================================
# generate a RSA key-pair
#=====================================
def RSAKeyPair(keylength):
    keyPair = RSA.generate(keylength)
    return keyPair

# Alice generates a RSA key-pair 
AliceKeyPair = RSAKeyPair(1024)


# Alice's public-key
pubKey = AliceKeyPair.publickey()
print(f"public-key:  (n={hex(pubKey.n)}, e={hex(pubKey.e)})")

# Alice's public-key in PEM format
# PEM format Base64 encodes the key
pubKeyPEM = AliceKeyPair.publickey().exportKey()
print("PubKey PEM Format: " +pubKeyPEM.decode('ascii'))

# Alice's private key
print(f"Private key: (n={hex(pubKey.n)}, d={hex(AliceKeyPair.d)})")

# Alice's private key in PEM format
privKeyPEM = AliceKeyPair.exportKey()
print("PRIVATE KEY PEM FORMAT; " + privKeyPEM.decode('ascii'))


#======================================================
# Smith encrypts a message using Alice's public-key
# message must be a binary string
#======================================================
message = b"The quick brown fox jumped over the farmer's hedge"
cipher = PKCS1_OAEP.new(pubKey)
cipherText = cipher.encrypt(message)
print("CipherText: ", binascii.hexlify(cipherText))


#=======================================================
# Alice decrypts Smith's message using her private key
#=======================================================
decipher = PKCS1_OAEP.new(AliceKeyPair)
plainText = decipher.decrypt(cipherText)
print('Decrypted Text: ', plainText)


#==========================================================
# Alice signs a message by first generating the SHA-256 
# digest of the message and then encrypting it with her
# private key.
# the string message is converted to a binary string
#==========================================================
message = b'let sleeping dogs lie, said the farmer'

hash = int.from_bytes(sha256(message).digest(), byteorder='big')
signature = pow(hash, AliceKeyPair.d, AliceKeyPair.n)
print("Alice's Signature:", hex(signature))


#============================================================
# Smith Verifies the signature by comparing the SHA-256 hash
# generated from the received message with the hash obtained
# by decrypting the signature received from Alice 
#=============================================================
hashFromMessage = int.from_bytes(sha256(message).digest(), byteorder='big')
decryptedHash   = pow(signature, AliceKeyPair.e, AliceKeyPair.n)

if (hashFromMessage == decryptedHash): 
   print("Signature is valid")
else:
   print("signature is invalid")