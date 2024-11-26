#email_user = "selecaomoda@gmail.com"
#email_pass = "ulnz ksdq wozm xzrk"

import imaplib
import email
from email.header import decode_header
import os
from flask import jsonify

def main():
    # Configurações do servidor IMAP do Gmail
    imap_server = "imap.gmail.com"
    email_user = "selecaomoda@gmail.com"
    email_pass = "ulnz ksdq wozm xzrk"

    # Conecte-se ao servidor IMAP do Gmail
    mail = imaplib.IMAP4_SSL(imap_server)
    mail.login(email_user, email_pass)

    # Selecionar a caixa de entrada (inbox)
    mail.select("inbox")
    
    # Lista para armazenar os nomes dos arquivos baixados
    downloaded_curriculos = []

    # Procurar por e-mails não lidos
    status, email_ids = mail.search(None, 'UNSEEN')

    # Verifique se a busca foi bem-sucedida
    if status != 'OK':
        print("Não foi possível buscar os e-mails.")
        mail.logout()
        exit()

    # Obtenha os IDs dos e-mails
    email_id_list = email_ids[0].split()

    # Diretório onde os anexos serão salvos
    download_dir = "curriculos"

    # Crie o diretório se não existir
    os.makedirs(download_dir, exist_ok=True)

    # Iterar sobre os IDs dos e-mails
    for email_id in email_id_list:
        # Buscar o e-mail pelo ID
        res, msg_data = mail.fetch(email_id, '(RFC822)')
        if res != 'OK':
            print(f"Erro ao buscar o e-mail com ID {email_id.decode('utf-8')}.")
            continue

        # Obter o conteúdo do e-mail
        email_body = msg_data[0][1]
        email_message = email.message_from_bytes(email_body)

        # Verificar se o e-mail tem anexos
        if email_message.get_content_maintype() == 'multipart':
            for part in email_message.walk():
                if part.get('Content-Disposition') is None:
                    continue

                filename = part.get_filename()
                if filename:
                    decoded_filename, charset = decode_header(filename)[0]
                    if isinstance(decoded_filename, bytes):
                        # Decodificar o nome do arquivo com o charset correto
                        decoded_filename = decoded_filename.decode(charset or 'utf-8')
                    # Verifique se o arquivo é PDF ou DOCX
                    if decoded_filename.lower().endswith(('.pdf', '.docx')):
                        filepath = os.path.join(download_dir, decoded_filename)
                        print(f"Baixando anexo: {decoded_filename}")
                        with open(filepath, 'wb') as f:
                            f.write(part.get_payload(decode=True))
                        # Adicionar nome do arquivo à lista
                        downloaded_curriculos.append(decoded_filename)
                            
                

        # Marcar o e-mail como lido
        mail.store(email_id, '+FLAGS', '\\Seen')

    # Fechar a conexão com o servidor IMAP
    mail.logout()
    print("Conexão encerrada.")
    print("Todos os currículos foram baixados com sucesso!")
    return downloaded_curriculos  # Retornar a lista de currículos baixados

if __name__ == '__main__':
    main()
