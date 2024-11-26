from flask import Flask, abort, render_template, request, jsonify, send_from_directory
from flask_assets import Environment, Bundle
import os
import buscar
import json
from werkzeug.utils import secure_filename
import traceback
from datetime import datetime
import gmail
from flask_cors import CORS
import logging
from collections import defaultdict

# Configuração básica do logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
CORS(app)

# Bundling CSS files
assets = Environment(app)
css = Bundle("src/css/*.css", filters="postcss", output="dist/css/output.css")
assets.register("css", css)
assets.init_app(app)

# Caminho absoluto do diretório atual onde o Flask está sendo executado
diretorio_atual = os.path.dirname(os.path.abspath(__file__))

# Caminho para a pasta "PERFIS" no mesmo diretório onde o Flask está sendo executado
PERFIS_DIR = os.path.join(diretorio_atual, "PERFIS")


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/criar_perfil")
def criar_perfil():
    return render_template("perfil.html")


@app.route("/analisar")
def analisar():
    return render_template("index.html")


@app.route("/agenda")
def agenda():
    return render_template("agenda.html", active_page="agenda")


@app.route("/salvar_perfil", methods=["POST"])
def salvar_perfil():
    dados = request.get_json()
    if not dados:
        return jsonify({"mensagem": "Nenhum dado foi recebido."}), 400
    nome_perfil = dados.get("nome_perfil")
    perfil = dados.get("perfil")
    if (
        not nome_perfil
        or not perfil
        or not perfil.get("descricao_vaga")
        or not perfil.get("pesos_palavras_chave")
    ):
        return jsonify({"mensagem": "Dados incompletos para o perfil."}), 400
    buscar.salvar_perfil(nome_perfil, perfil)
    return jsonify({"mensagem": "Perfil salvo com sucesso!"})


@app.route("/PERFIS", methods=["GET"])
def listar_perfis_json():
    perfis = [
        perfil.replace(".json", "")
        for perfil in os.listdir(PERFIS_DIR)
        if perfil.endswith(".json")
    ]
    return jsonify(perfis)


@app.route("/listar_perfis", methods=["GET"])
def listar_perfis():
    perfis = buscar.listar_perfis_disponiveis()
    return jsonify(perfis)


@app.route("/carregar_perfil", methods=["POST"])
def carregar_perfil():
    nome_perfil = request.json["nome_perfil"]
    perfil = buscar.carregar_perfil(nome_perfil)
    return jsonify(perfil)


@app.route("/PERFIS/<nome_perfil>.json")
def perfil_json(nome_perfil):
    caminho_perfil = os.path.join(PERFIS_DIR, f"{nome_perfil}.json")
    if os.path.exists(caminho_perfil):
        return send_from_directory(PERFIS_DIR, f"{nome_perfil}.json")
    else:
        return jsonify({"mensagem": "Perfil não encontrado"}), 404


@app.route("/analisar_curriculos", methods=["POST"])
def analisar_curriculos():
    perfil_selecionado = request.form.get(
        "perfilSelecionado"
    )  # Pega o perfil selecionado do form data
    resultados_gerais = []

    # Obter os currículos enviados no formulário
    arquivos_curriculos = request.files.getlist("arquivos_curriculos")

    # Carrega o perfil selecionado uma única vez
    perfil = buscar.carregar_perfil(perfil_selecionado)
    descricao_vaga = perfil.get("descricao_vaga", "")
    pesos_palavras_chave = perfil.get("pesos_palavras_chave", {})
    descricao_tokens = buscar.preprocess(descricao_vaga)

    for arquivo in arquivos_curriculos:
        if arquivo and arquivo.filename:
            try:
                texto_curriculo = buscar.extract_text(arquivo)
                curriculo_tokens = buscar.preprocess(texto_curriculo)
                final_score = buscar.calcular_pontuacao(
                    curriculo_tokens, descricao_tokens, pesos_palavras_chave
                )
                resultado = {
                    "nome_curriculo": arquivo.filename,
                    "perfil_analisado": perfil_selecionado,
                    "pontuacao_final": final_score,
                }
                resultados_gerais.append(resultado)
                # Registrar no db.json
                buscar.registrar_resultado(
                    perfil_selecionado, arquivo.filename, final_score
                )
            except Exception as e:
                print(f"Erro ao processar o currículo {arquivo.filename}: {e}")
                traceback.print_exc()
                resultado = {
                    "nome_curriculo": arquivo.filename,
                    "perfil_analisado": perfil_selecionado,
                    "pontuacao_final": "Não foi possível analisar",
                }
                resultados_gerais.append(resultado)

    # Ordenar e retornar os resultados
    resultados_gerais.sort(
        key=lambda x: (
            x["pontuacao_final"] if isinstance(x["pontuacao_final"], float) else -1
        ),
        reverse=True,
    )
    return jsonify(resultados_gerais)


@app.route("/resultados", methods=["GET"])
def obter_resultados():
    try:
        with open(os.path.join(diretorio_atual, "db.json"), "r") as db_file:
            dados = json.load(db_file)
        return jsonify(dados)
    except FileNotFoundError:
        return jsonify([]), 404


@app.route("/executar_gmail")
def executar_gmail():
    try:
        curriculos = (
            gmail.main()
        )  # Chamar a função main do gmail.py e obter a lista de currículos baixados
        mensagem = "Todos os currículos baixados com sucesso!"
        return jsonify(
            {"mensagem": mensagem, "curriculos": curriculos, "success": True}
        )
    except Exception as e:
        mensagem = f"Ocorreu um erro: {e}"
        return jsonify({"mensagem": mensagem, "success": False})


@app.route("/salvar_entrevista", methods=["POST"])
def salvar_entrevista():
    try:
        if request.content_type != "application/json":
            return (
                jsonify({"success": False, "error": "Tipo de conteúdo inválido."}),
                400,
            )

        dados_entrevista = request.json
        print(
            "Dados recebidos:", dados_entrevista
        )  # Log para verificar os dados recebidos

        arquivo_entrevistas = os.path.join(diretorio_atual, "entrevistas.json")
        entrevistas = []

        # Verifica se o arquivo existe e carrega as entrevistas existentes
        if os.path.exists(arquivo_entrevistas):
            with open(arquivo_entrevistas, "r") as file:
                entrevistas = json.load(file)
        else:
            print("Arquivo de entrevistas não existe. Será criado um novo.")

        entrevistas.append(
            {
                "candidato": dados_entrevista["title"],
                "data": dados_entrevista["start"],
                "nomeCurriculo": dados_entrevista["nomeCurriculo"],
                "perfil": dados_entrevista["perfilSelecionado"],
            }
        )

        # Reescreve o arquivo com as entrevistas atualizadas
        with open(arquivo_entrevistas, "w") as file:
            json.dump(entrevistas, file, indent=4)

        return jsonify({"success": True})

    except Exception as e:
        print(f"Erro ao salvar entrevista: {e}")
        traceback.print_exc()  # Isso vai imprimir o traceback completo no console
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/entrevistas_mes/<mesAno>", methods=["GET"])
def entrevistas_mes(mesAno):
    # Captura o parâmetro de query 'origem' com um valor padrão se ele não for fornecido
    origem = request.args.get('origem', 'agenda')

    try:
        with open("entrevistas.json", "r") as file:
            todas_entrevistas = json.load(file)

        # Filtra entrevistas com base na origem da solicitação
        if origem == 'agenda':
            entrevistas_filtradas = [
                entrevista for entrevista in todas_entrevistas if entrevista["data"].startswith(mesAno)
            ]
        elif origem == 'acompanhamento':
            mes, ano = mesAno.split('-')
            entrevistas_filtradas = [
                entrevista for entrevista in todas_entrevistas
                if entrevista["data"][5:7] == mes and entrevista["data"][:4] == ano
            ]
        else:
            return jsonify({"error": "Origem desconhecida."}), 400

        return jsonify(entrevistas_filtradas)
    except FileNotFoundError:
        return jsonify([]), 404
    except json.JSONDecodeError:
        return jsonify({"error": "Bad JSON format in entrevistas.json"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500




@app.route("/curriculos/<filename>")
def curriculos(filename):
    return send_from_directory("curriculos", filename)


@app.route("/atualizar_perfil", methods=["POST"])
def atualizar_perfil():
    dados = request.get_json()
    nome_perfil = dados["nome_perfil"]
    palavra_antiga = dados["palavra_antiga"]
    nova_palavra = dados["nova_palavra"]
    nova_pontuacao = float(dados["pontuacao"])  # Converte para float

    caminho_perfil = os.path.join(PERFIS_DIR, f"{nome_perfil}.json")
    if not os.path.exists(caminho_perfil):
        return jsonify({"mensagem": "Perfil não encontrado"}), 404

    with open(caminho_perfil, "r+") as file:
        perfil = json.load(file)
        # Se a palavra chave foi alterada, atualize a chave no dicionário
        if palavra_antiga != nova_palavra:
            perfil["pesos_palavras_chave"].pop(palavra_antiga, None)
            perfil["pesos_palavras_chave"][nova_palavra] = nova_pontuacao
        else:
            perfil["pesos_palavras_chave"][palavra_antiga] = nova_pontuacao

        file.seek(0)
        file.truncate()
        json.dump(perfil, file, indent=4)

    return jsonify({"mensagem": "Perfil atualizado com sucesso!"})


@app.route("/remover_palavra_chave", methods=["POST"])
def remover_palavra_chave():
    dados = request.get_json()
    nome_perfil = dados["nome_perfil"]
    palavra_chave = dados["palavra_chave"]

    caminho_perfil = os.path.join(PERFIS_DIR, f"{nome_perfil}.json")
    if not os.path.exists(caminho_perfil):
        return jsonify({"mensagem": "Perfil não encontrado"}), 404

    with open(caminho_perfil, "r+") as file:
        perfil = json.load(file)
        perfil["pesos_palavras_chave"].pop(palavra_chave, None)

        file.seek(0)
        file.truncate()
        json.dump(perfil, file, indent=4)

    return jsonify(
        {"mensagem": f"Palavra-chave '{palavra_chave}' removida com sucesso!"}
    )


@app.route("/atualizar_descricao", methods=["POST"])
def atualizar_descricao():
    dados = request.json
    nova_descricao = dados["novaDescricao"]
    nome_perfil = dados["nomePerfil"]  # Nome do perfil para encontrar o arquivo correto

    caminho_arquivo = os.path.join("PERFIS", f"{nome_perfil}.json")

    # Verifica se o arquivo existe
    if not os.path.exists(caminho_arquivo):
        return jsonify({"mensagem": "Perfil não encontrado!"}), 404

    # Lê o arquivo existente
    with open(caminho_arquivo, "r") as arquivo:
        perfil = json.load(arquivo)

    # Atualiza a descrição da vaga
    perfil["descricao_vaga"] = nova_descricao

    # Salva as alterações de volta no arquivo
    with open(caminho_arquivo, "w") as arquivo:
        json.dump(perfil, arquivo, indent=4)

    return jsonify({"mensagem": "Descrição atualizada com sucesso!"})


@app.route("/adicionar_palavra_chave/<perfil_nome>", methods=["POST"])
def adicionar_palavra_chave(perfil_nome):
    dados = request.get_json()
    nova_palavra = dados["nova_palavra"]
    nova_pontuacao = float(dados["pontuacao"])  # Converte para float

    caminho_perfil = os.path.join(PERFIS_DIR, f"{perfil_nome}.json")
    if not os.path.exists(caminho_perfil):
        return jsonify({"mensagem": "Perfil não encontrado"}), 404

    with open(caminho_perfil, "r+") as file:
        perfil = json.load(file)
        # Adiciona a nova palavra-chave e pontuação
        perfil["pesos_palavras_chave"][nova_palavra] = nova_pontuacao

        file.seek(0)
        file.truncate()
        json.dump(perfil, file, indent=4)

    return jsonify({"mensagem": "Palavra-chave adicionada com sucesso ao perfil!"})


@app.route("/cancelar_entrevista", methods=["POST"])
def cancelar_entrevista():
    dados = request.get_json()
    nome_candidato = dados.get("nomeCandidato")
    if not nome_candidato:
        return (
            jsonify({"success": False, "message": "Nome do candidato não fornecido."}),
            400,
        )
    try:
        arquivo_entrevistas = os.path.join(diretorio_atual, "entrevistas.json")
        # Verifica se o arquivo existe
        if not os.path.isfile(arquivo_entrevistas):
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Arquivo de entrevistas não encontrado.",
                    }
                ),
                404,
            )
        with open(arquivo_entrevistas, "r") as file:
            entrevistas = json.load(file)
        entrevistas = [
            entrevista
            for entrevista in entrevistas
            if entrevista["candidato"] != nome_candidato
        ]
        
        # Salvar de volta no arquivo JSON
        with open(arquivo_entrevistas, "w") as file:
            json.dump(entrevistas, file, indent=4)
        return jsonify(
            {"success": True, "message": "Entrevista cancelada com sucesso."}
        )
    except json.JSONDecodeError as e:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Formato de arquivo de entrevistas inválido.",
                }
            ),
            500,
        )
        
    except Exception as e:
        # Em um ambiente de produção, evite enviar descrições de erro detalhadas ao cliente
        # Use o logging para registrar o erro no servidor
        return (
            jsonify({"success": False, "message": "Erro ao processar a solicitação."}),
            500,
        )


@app.route("/entrevistas", methods=["GET"])
def obter_entrevistas():
    mes_query = request.args.get('mes')
    ano_atual = datetime.now().year  # Obtém o ano atual
    try:
        with open("entrevistas.json", "r") as file:
            entrevistas = json.load(file)

        if mes_query:  # Se houver uma query de mês, filtra pelo mês
            mes_query = int(mes_query)
            entrevistas = [
                ent for ent in entrevistas
                if datetime.strptime(ent['data'], '%Y-%m-%dT%H:%M').month == mes_query
            ]
        else:  # Se não, retorna todas as entrevistas do ano atual
            entrevistas = [
                ent for ent in entrevistas
                if datetime.strptime(ent['data'], '%Y-%m-%dT%H:%M').year == ano_atual
            ]

        return jsonify(entrevistas)
    except FileNotFoundError:
        return jsonify([]), 404
    except json.JSONDecodeError:
        return jsonify({"error": "Erro no formato do JSON."}), 500


@app.route("/acompanhamento")
def acompanhamento():
    return render_template("acompanhamento.html", active_page="acompanhamento")


@app.route("/salvar_observacao", methods=["POST"])
def salvar_observacao():
    dados = request.get_json()
    nome_candidato = dados.get("candidato")
    observacao = dados.get("observacao")
    try:
        with open("entrevistas.json", "r+") as file:
            entrevistas = json.load(file)
            # Encontra a entrevista e atualiza a observação
            for entrevista in entrevistas:
                if entrevista["candidato"] == nome_candidato:
                    entrevista["observacao"] = observacao
                    break
            file.seek(0)
            file.truncate()
            json.dump(entrevistas, file, indent=4)
        return jsonify({"success": True, "message": "Observação atualizada com sucesso."})
    except FileNotFoundError:
        return jsonify({"error": "Arquivo não encontrado."}), 404
    except json.JSONDecodeError:
        return jsonify({"error": "Erro no formato do JSON."}), 500
    
    
    
@app.route("/entrevistas_com_observacoes", methods=["GET"])
def entrevistas_com_observacoes():
    try:
        with open("entrevistas.json", "r") as file:
            entrevistas = json.load(file)
            # Filtra apenas as entrevistas que têm observações e não estão contratadas
            entrevistasComObs = [ent for ent in entrevistas if "observacao" in ent and ent["observacao"].strip() and not ent.get("contratado", False)]
        return jsonify(entrevistasComObs)
    except FileNotFoundError:
        return jsonify({"error": "Arquivo não encontrado."}), 404
    except json.JSONDecodeError:
        return jsonify({"error": "Erro no formato do JSON."}), 500

    
    
    
def atualizar_arquivo_entrevistas(arquivo, candidato, status):
    with open(arquivo, "r+") as file:
        entrevistas = json.load(file)
        for entrevista in entrevistas:
            if entrevista["candidato"] == candidato:
                entrevista["contratado"] = status
                break
        file.seek(0)
        file.truncate()
        json.dump(entrevistas, file, indent=4)
    return True



@app.route("/admitir_candidato", methods=["POST"])
def admitir_candidato():
    dados = request.get_json()
    nome_candidato = dados.get("candidato")
    origem = dados.get("origem")
    loja = dados.get("loja")
    cargo = dados.get("cargo")
    data_admissao = dados.get("dataAdmissao")

    if not nome_candidato:
        return jsonify({"success": False, "message": "Nome do candidato não fornecido."}), 400
    if not data_admissao:
        return jsonify({"success": False, "message": "Data de admissão inválida."}), 400

    try:
        with open("entrevistas.json", "r+") as file:
            entrevistas = json.load(file)
            entrevista_existente = False
            for entrevista in entrevistas:
                if entrevista.get("candidato") == nome_candidato:
                    entrevista_existente = True
                    entrevista.update({
                        "origem": origem,
                        "loja": loja,
                        "cargo": cargo,
                        "dataAdmissao": data_admissao,
                        "admitido": True,
                        "contratado": False
                    })
                    break
            if not entrevista_existente:
                entrevistas.append({
                    "candidato": nome_candidato,
                    "origem": origem,
                    "loja": loja,
                    "cargo": cargo,
                    "dataAdmissao": data_admissao,
                    "admitido": True,
                    "contratado": False
                })

            file.seek(0)
            file.truncate()
            json.dump(entrevistas, file, indent=4)

        return jsonify({"success": True, "message": "Candidato admitido com sucesso."})
    except FileNotFoundError:
        return jsonify({"success": False, "message": "Arquivo não encontrado."}), 404
    except json.JSONDecodeError:
        return jsonify({"success": False, "message": "Erro no formato do JSON."}), 500




@app.route("/historico_admissoes", methods=["GET"])
def historico_admissoes():
    try:
        with open("entrevistas.json", "r") as file:
            entrevistas = json.load(file)
            admitidos = [ent for ent in entrevistas if ent.get('admitido')]
        return jsonify(admitidos)
    except FileNotFoundError:
        return jsonify({"error": "Arquivo não encontrado"}), 404
    except json.JSONDecodeError:
        return jsonify({"error": "Erro no formato do JSON"}), 500

    
    
    
@app.route("/excluir_observacao", methods=["POST"])
def excluir_observacao():
    dados = request.get_json()
    nome_candidato = dados.get("candidato")
    try:
        with open("entrevistas.json", "r+") as file:
            entrevistas = json.load(file)
            for entrevista in entrevistas:
                if entrevista["candidato"] == nome_candidato:
                    entrevista["observacao"] = ""  # Ou use `del entrevista["observacao"]` para remover a chave
            file.seek(0)
            file.truncate()
            json.dump(entrevistas, file, indent=4)
        return jsonify({"success": True, "message": "Observação excluída com sucesso."})
    except FileNotFoundError:
        return jsonify({"success": False, "message": "Arquivo não encontrado."}), 404
    except json.JSONDecodeError:
        return jsonify({"success": False, "message": "Erro no formato do JSON."}), 500

    

@app.route("/contratar_candidato", methods=["POST"])
def contratar_candidato():
    dados = request.get_json()
    nome_candidato = dados.get("candidato")
    data_contratacao = dados.get("dataContratacao")

    if not nome_candidato or not data_contratacao:
        return jsonify({"success": False, "message": "Dados incompletos."}), 400

    try:
        with open("entrevistas.json", "r+") as file:
            entrevistas = json.load(file)
            for entrevista in entrevistas:
                if entrevista.get("candidato") == nome_candidato:
                    entrevista.update({
                        "admitido": False,
                        "contratado": True,
                        "dataContratacao": data_contratacao
                    })
                    file.seek(0)
                    file.truncate()
                    json.dump(entrevistas, file, indent=4)
                    return jsonify({
                        "success": True,
                        "message": "Candidato contratado com sucesso.",
                        "candidato": entrevista  # Aqui retornamos o objeto atualizado
                    })
            # Se não encontrar o candidato, retorna erro
            return jsonify({"success": False, "message": "Candidato não encontrado."}), 404
    except FileNotFoundError:
        return jsonify({"success": False, "message": "Arquivo não encontrado."}), 404
    except json.JSONDecodeError:
        return jsonify({"success": False, "message": "Erro no formato do JSON."}), 500


@app.route("/historico_contratacoes", methods=["GET"])
def historico_contratacoes():
    try:
        with open("entrevistas.json", "r") as file:
            entrevistas = json.load(file)
            contratados = [ent for ent in entrevistas if ent.get('contratado')]
        return jsonify(contratados)
    except FileNotFoundError:
        return jsonify({"error": "Arquivo não encontrado"}), 404
    except json.JSONDecodeError:
        return jsonify({"error": "Erro no formato do JSON"}), 500


@app.route("/dispensar_candidato", methods=["POST"])
def dispensar_candidato():
    dados = request.get_json()
    nome_candidato = dados.get("candidato")
    motivo_dispensa = dados.get("motivo")
    data_dispensa = dados.get("dataDispensa")

    if not nome_candidato or not data_dispensa:
        return jsonify({"success": False, "message": "Informações do candidato ou data de dispensa não fornecidas."}), 400

    try:
        with open("entrevistas.json", "r+") as file:
            entrevistas = json.load(file)
            candidato_encontrado = None
            for entrevista in entrevistas:
                if entrevista.get("candidato") == nome_candidato:
                    entrevista.update({
                        "admitido": False,
                        "contratado": False,
                        "dispensado": True,
                        "motivoDispensa": motivo_dispensa,
                        "dataDispensa": data_dispensa
                    })
                    candidato_encontrado = entrevista
                    break

            if not candidato_encontrado:
                return jsonify({"success": False, "message": "Candidato não encontrado para dispensa."}), 404

            file.seek(0)
            file.truncate()
            json.dump(entrevistas, file, indent=4)

        return jsonify({"success": True, "candidato": candidato_encontrado}), 200
    except FileNotFoundError:
        return jsonify({"success": False, "message": "Arquivo de entrevistas não encontrado."}), 404
    except json.JSONDecodeError:
        return jsonify({"success": False, "message": "Erro ao processar o arquivo JSON."}), 500
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/historico_dispensas", methods=["GET"])
def historico_dispensas():
    try:
        with open("entrevistas.json", "r") as file:
            entrevistas = json.load(file)
            dispensados = [ent for ent in entrevistas if ent.get('dispensado')]
        return jsonify(dispensados)
    except FileNotFoundError:
        return jsonify({"error": "Arquivo não encontrado"}), 404
    except json.JSONDecodeError:
        return jsonify({"error": "Erro no formato do JSON"}), 500


@app.route("/dispensar_contratado", methods=["POST"])
def dispensar_contratado():
    dados = request.get_json()
    nome_candidato = dados.get("candidato")
    motivo_dispensa = dados.get("motivoDispensa")
    data_dispensa = dados.get("dataDispensa")

    if not nome_candidato or not motivo_dispensa or not data_dispensa:
        return jsonify({"success": False, "message": "Informações do candidato ou data de dispensa não fornecidas."}), 400

    try:
        with open("entrevistas.json", "r+") as file:
            entrevistas = json.load(file)
            candidato_encontrado = None
            for entrevista in entrevistas:
                if entrevista.get("candidato") == nome_candidato and entrevista.get("contratado"):
                    entrevista.update({
                        "contratado": False,
                        "dispensado": True,
                        "motivoDispensa": motivo_dispensa,
                        "dataDispensa": data_dispensa
                    })
                    candidato_encontrado = entrevista
                    break

            if not candidato_encontrado:
                return jsonify({"success": False, "message": "Candidato contratado não encontrado para dispensa."}), 404

            file.seek(0)
            file.truncate()
            json.dump(entrevistas, file, indent=4)

        return jsonify({"success": True, "candidato": candidato_encontrado}), 200
    except FileNotFoundError:
        return jsonify({"success": False, "message": "Arquivo de entrevistas não encontrado."}), 404
    except json.JSONDecodeError:
        return jsonify({"success": False, "message": "Erro ao processar o arquivo JSON."}), 500
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500



@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')


@app.route('/calcular-metricas', methods=['GET'])
def calcular_metricas():
    inicio = request.args.get('inicio', type=str)
    fim = request.args.get('fim', type=str)
    loja = request.args.get('loja', default='todas', type=str).strip().lower()

    try:
        inicio_periodo = datetime.strptime(inicio, '%d/%m/%Y')
        fim_periodo = datetime.strptime(fim, '%d/%m/%Y')
    except ValueError as e:
        return jsonify({"error": "Invalid date format. Please use DD/MM/YYYY."}), 400

    try:
        with open('entrevistas.json', 'r') as file:
            entrevistas = json.load(file)
    except Exception as e:
        return jsonify({"error": "Error reading from the file."}), 500

    entrevistas_no_periodo = [
        e for e in entrevistas if inicio_periodo <= datetime.strptime(e['dataAdmissao'], '%Y-%m-%d') <= fim_periodo
        and (loja == 'todas' or e['loja'].strip().lower() == loja)
    ]

    total_candidatos = len(entrevistas_no_periodo)
    admissao = sum(1 for e in entrevistas_no_periodo if e.get('admitido'))
    dispensa_pessoal = sum(1 for e in entrevistas_no_periodo if e.get('motivoDispensa', '').replace(' ', '').lower() == 'dispensapessoal')
    dispensa_empresa = sum(1 for e in entrevistas_no_periodo if e.get('motivoDispensa', '').replace(' ', '').lower() == 'dispensaempresa')
    total_dispensados = dispensa_pessoal + dispensa_empresa

    total_dias_permanencia = sum(
        calcular_tempo_permanencia(e['dataAdmissao'], e.get('dataDispensa', datetime.now().strftime('%Y-%m-%d')))
        for e in entrevistas_no_periodo if e.get('dispensado')
    )
    possiveis_origens = ['Indeed', 'Indicação', 'Vagas Floripa', 'Instagram', 'Entregue na loja', 'Abordagem']
    origens = {origem: 0 for origem in possiveis_origens}

    for entrevista in entrevistas_no_periodo:
        origem = entrevista.get('origem', 'Desconhecida')
        if origem in origens:
            origens[origem] += 1

    metricas = {
        'rotatividade': ((admissao + total_dispensados) / (total_candidatos if total_candidatos > 0 else 1)) * 100,
        'turnover_ativos': (dispensa_pessoal / (total_candidatos if total_candidatos > 0 else 1)) * 100,
        'turnover_passivos': (dispensa_empresa / (total_candidatos if total_candidatos > 0 else 1)) * 100,
        'turnover_geral': (total_dispensados / (total_candidatos if total_candidatos > 0 else 1)) * 100,
        'media_permanencia': (total_dias_permanencia / (total_dispensados if total_dispensados > 0 else 1)),
        'admissoes': admissao,
        'contratados': sum(1 for e in entrevistas_no_periodo if e.get('contratado')),
        'dispensa_empresa': dispensa_empresa,
        'dispensa_pessoal': dispensa_pessoal,
        'em_experiencia': sum(1 for e in entrevistas_no_periodo if e.get('admitido') and not e.get('motivoDispensa')),
        'quadro_geral': sum(1 for e in entrevistas_no_periodo if (e.get('admitido') or e.get('contratado')) and not e.get('dispensado')),
        'percentual_experiencia': (sum(1 for e in entrevistas_no_periodo if e.get('admitido') and not e.get('motivoDispensa')) / (total_candidatos if total_candidatos > 0 else 1)) * 100,
        'origens': origens
    }

   
    return jsonify(metricas)


def calcular_tempo_permanencia(data_inicio, data_fim):
    data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
    data_fim = datetime.strptime(data_fim, '%Y-%m-%d')
    return (data_fim - data_inicio).days


@app.route('/dados-origem', methods=['GET'])
def dados_origem():
    inicio = request.args.get('inicio', type=str)
    fim = request.args.get('fim', type=str)
    loja = request.args.get('loja', default='todas', type=str).strip().lower()

    try:
        inicio_periodo = datetime.strptime(inicio, '%Y-%m-%d')
        fim_periodo = datetime.strptime(fim, '%Y-%m-%d')
    except ValueError as e:
        return jsonify({"error": "Invalid date format. Please use YYYY-MM-DD."}), 400

    try:
        with open('entrevistas.json', 'r') as file:
            entrevistas = json.load(file)
    except Exception as e:
        return jsonify({"error": "Error reading from the file."}), 500

    contagem_origem = {}
    for entrevista in entrevistas:
        if "dataAdmissao" in entrevista and (loja == 'todas' or entrevista['loja'].strip().lower() == loja):
            data_admissao = datetime.strptime(entrevista['dataAdmissao'], '%Y-%m-%d')
            if inicio_periodo <= data_admissao <= fim_periodo:
                origem = entrevista.get('origem', 'Desconhecida')
                if origem in contagem_origem:
                    contagem_origem[origem] += 1
                else:
                    contagem_origem[origem] = 1

    return jsonify(contagem_origem)


@app.route('/calcular-rotatividade-todas-lojas', methods=['GET'])
def calcular_rotatividade_todas_lojas():
    inicio = request.args.get('inicio', type=str)
    fim = request.args.get('fim', type=str)
    
    try:
        inicio_periodo = datetime.strptime(inicio, '%d/%m/%Y')
        fim_periodo = datetime.strptime(fim, '%d/%m/%Y')
    except ValueError:
        return jsonify({"error": "Invalid date format. Please use DD/MM/YYYY."}), 400

    todas_lojas = ["Store", "Kobrasol", "Boutique", "Esteves", "Tenente", "Outlet", "Logística", "Financeiro"]
    resultados = {}
    
    try:
        with open('entrevistas.json', 'r') as file:
            entrevistas = json.load(file)
        
        for loja in todas_lojas:
            entrevistas_loja = [e for e in entrevistas if e.get('loja', '').lower() == loja.lower()]
            total_candidatos = len(entrevistas_loja)
            eventos_relevantes = 0

            for e in entrevistas_loja:
                data_admissao = datetime.strptime(e['dataAdmissao'], '%Y-%m-%d')
                if 'dataDispensa' in e:
                    data_dispensa = datetime.strptime(e['dataDispensa'], '%Y-%m-%d')
                else:
                    data_dispensa = None

                if inicio_periodo <= data_admissao <= fim_periodo:
                    eventos_relevantes += 1
                if data_dispensa and inicio_periodo <= data_dispensa <= fim_periodo:
                    eventos_relevantes += 1
            
            if total_candidatos > 0:
                rotatividade = (eventos_relevantes / total_candidatos) * 100
            else:
                rotatividade = 0
            
            resultados[loja] = round(rotatividade, 2)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
    return jsonify(resultados)



if __name__ == "__main__":
    app.run(debug=True)
