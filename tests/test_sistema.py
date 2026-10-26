"""Teste rápido do sistema inteiro: abre todas as páginas e confere os fluxos principais.

Como rodar (na pasta do projeto, com o ambiente virtual ativo):
    python -m unittest tests.test_sistema -v

Usa um banco temporário próprio; NÃO toca em instance/fmabc_eventos.db.
"""
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="fmabc_teste_")
# Anexos do teste vão para uma pasta temporária, nunca para instance/anexos.
os.environ["FMABC_ANEXOS_DIR"] = str(Path(_TMP) / "anexos")
# Nunca enviar e-mails reais durante o teste, mesmo que o .env tenha SMTP configurado.
os.environ["SMTP_HOST"] = ""
os.environ["SMTP_FROM"] = ""
os.environ["LEMBRETES_AUTOMATICOS"] = "0"
os.environ["DATABASE_PATH"] = str(Path(_TMP) / "teste.db")
os.environ["ADMIN_EMAIL"] = "admin@teste.br"
os.environ["ADMIN_PASSWORD"] = "senha-teste-123"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as sistema  # noqa: E402


class SistemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sistema.app.config["PROPAGATE_EXCEPTIONS"] = False
        cls.client = sistema.app.test_client()
        cls.client.get("/login")
        cls._post(cls, "/login", {"email": "admin@teste.br", "password": "senha-teste-123"})
        publico = sistema.app.test_client()
        publico.get("/solicitar")
        dados = {
            "organizer_email": "solicitante@fmabc.br", "contact_email": "contato@fmabc.br", "start_date": "2099-05-10",
            "title": "Evento de teste", "start_time": "09h00", "end_time": "12h00", "department": "Teste",
            "organizer_name": "Pessoa Teste", "audience": "Alunos", "expected_attendees": "80", "description": "Teste",
            "organizer_phone": "11999999999", "authorized_by": "Reitoria", "cost_center": "000",
            "event_category": "Congresso / Simpósio", "event_modes": "Presencial", "support": "TI",
            "venues": "Salão Nobre - 81 lugares", "requested_items": "Coffee break",
        }
        cls._post(cls, "/solicitar", dados, publico)
        cls._post(cls, "/eventos/1/status", {"status": "aprovado", "priority": "Normal"})

    def _post(self, url, data, client=None):
        client = client or self.client
        with client.session_transaction() as s:
            token = s.get("_csrf")
        return client.post(url, data={**data, "_csrf": token})

    def test_todas_as_paginas_abrem(self):
        paginas = ["/", "/triagem", "/eventos", "/agenda", "/comunicacao", "/relatorios",
                   "/relatorios/comparativo-custos", "/relatorios/exportar.csv", "/checklist-consolidado",
                   "/modelos-checklist", "/cadastros-apoio", "/equipe", "/manual?q=mesa",
                   "/eventos/1", "/eventos/1/editar", "/eventos/1/roteiro", "/eventos/1/orcamento",
                   "/eventos/1/ocorrencias", "/eventos/1/finalizar", "/eventos/1/checklist/imprimir", "/espacos",
                   "/eventos/1/checklist", "/eventos/1/checklist?agrupar=etapa", "/eventos/1/checklist?agrupar=responsavel"]
        for url in paginas:
            with self.subTest(url=url):
                self.assertLess(self.client.get(url).status_code, 400, url)

    def test_orcamento_e_cotacao(self):
        self._post("/eventos/1/orcamento", {"action": "add", "item_name": "Coffee", "estimated_amount": "1.500",
                                            "contracted_amount": "1.400,00", "status": "previsto"})
        pagina = self.client.get("/eventos/1/orcamento").get_data(as_text=True)
        self.assertIn("1500,00", pagina)
        self.assertIn("1400,00", pagina)

    def test_leitura_de_valores_horarios_e_locais(self):
        self.assertEqual(sistema._parse_money("1.500"), 1500)
        self.assertEqual(sistema._parse_money("1.500,50"), 1500.5)
        self.assertEqual(sistema._time_values_to_minutes("7h às 17h"), [420, 1020])
        self.assertEqual(sistema._normalize_venue_key("Anfiteatro Dr. David Uip"),
                         sistema._normalize_venue_key("Auditório David Uip - 280 lugares"))

    def test_campo_personalizado(self):
        db = sistema.sqlite3.connect(os.environ["DATABASE_PATH"])
        template_id, task_id = db.execute("SELECT template_id, id FROM tasks WHERE event_id=1 AND template_id IS NOT NULL LIMIT 1").fetchone()
        self._post("/modelos-checklist", {"action": "add_field", "template_id": template_id,
                                          "field_label": "Pedido", "field_type": "text"})
        field_id = db.execute("SELECT id FROM task_template_fields WHERE template_id=?", (template_id,)).fetchone()[0]
        titulo = db.execute("SELECT title FROM tasks WHERE id=?", (task_id,)).fetchone()[0]
        self._post(f"/eventos/1/tarefas/{task_id}/editar", {"title": titulo, "status": "pendente", f"custom_field_{field_id}": "PC-1"})
        self.assertIn("PC-1", self.client.get("/eventos/1/checklist").get_data(as_text=True))

    def test_bloqueio_de_espaco_e_varios_dias(self):
        db = sistema.sqlite3.connect(os.environ["DATABASE_PATH"])
        venue_id = db.execute("SELECT id FROM venues WHERE name='Auditório David Uip'").fetchone()[0]
        self._post("/espacos", {"action": "add_block", "venue_id": venue_id, "block_start_date": "2099-06-01",
                                "block_end_date": "2099-06-02", "block_reason": "Manutenção"})
        publico = sistema.app.test_client()
        publico.get("/solicitar")
        resposta = publico.get("/api/agenda/verificar-reserva?start_date=2099-05-31&end_date=2099-06-01&start_time=09h00"
                               "&end_time=10h00&venues=Audit%C3%B3rio+David+Uip+-+280+lugares").get_json()
        self.assertTrue(resposta["conflict"])
        self.assertIn("Manutenção", resposta["message"])

    def test_comentario_e_anexo(self):
        import io
        self._post("/eventos/1/comentarios", {"comment": "Comentário de teste"})
        with self.client.session_transaction() as s:
            token = s.get("_csrf")
        self.client.post("/eventos/1/anexos", data={"_csrf": token, "category": "Outro",
                                                    "attachment": (io.BytesIO(b"conteudo"), "teste.txt")},
                         content_type="multipart/form-data")
        pagina = self.client.get("/eventos/1").get_data(as_text=True)
        self.assertIn("Comentário de teste", pagina)
        self.assertIn("teste.txt", pagina)

    def test_pedido_de_informacoes_e_caixa_de_saida(self):
        db = sistema.sqlite3.connect(os.environ["DATABASE_PATH"])
        self._post("/eventos/1/status", {"status": "aguardando_informacoes", "priority": "Normal",
                                         "notify_requester": "yes", "message_to_requester": "Envie o ofício."})
        token = db.execute("SELECT token FROM info_requests WHERE event_id=1 AND status='aberta'").fetchone()[0]
        publico = sistema.app.test_client()
        publico.get(f"/responder/{token}")
        with publico.session_transaction() as s:
            csrf = s.get("_csrf")
        publico.post(f"/responder/{token}", data={"_csrf": csrf, "answered_by": "Pessoa", "answer": "Segue."})
        self.assertEqual(db.execute("SELECT status FROM events WHERE id=1").fetchone()[0], "em_triagem")
        pagina = self.client.get("/emails").get_data(as_text=True)
        self.assertIn("Informações necessárias", pagina)

    def test_calendario_ics(self):
        self.client.get("/emails")
        db = sistema.sqlite3.connect(os.environ["DATABASE_PATH"])
        perto = (sistema.date.today() + sistema.timedelta(days=10)).isoformat()
        db.execute("UPDATE events SET start_date=?, end_date=? WHERE id=1", (perto, perto))
        db.commit()
        token = db.execute("SELECT ics_token FROM users WHERE email='admin@teste.br'").fetchone()[0]
        resposta = sistema.app.test_client().get(f"/agenda.ics?token={token}").get_data(as_text=True)
        self.assertIn("BEGIN:VCALENDAR", resposta)
        self.assertIn("Evento de teste", resposta)

    def test_checklist_um_clique_lote_e_observacao(self):
        db = sistema.sqlite3.connect(os.environ["DATABASE_PATH"])
        ids = [r[0] for r in db.execute("SELECT id FROM tasks WHERE event_id=1 ORDER BY id LIMIT 3").fetchall()]
        with self.client.session_transaction() as s:
            token = s.get("_csrf")
        r = self.client.post(f"/eventos/1/tarefas/{ids[0]}/alternar", data={"_csrf": token}, headers={"X-Requested-With": "fetch"})
        self.assertTrue(r.get_json()["task"]["done"])
        r = self.client.post(f"/eventos/1/tarefas/{ids[0]}/observacoes", data={"_csrf": token, "text": "Nota de teste"},
                             headers={"X-Requested-With": "fetch"})
        self.assertTrue(r.get_json()["ok"])
        self._post("/eventos/1/tarefas/lote", {"action": "atribuir", "task_ids": ids[1:], "assigned_to": "TI"})
        self.assertEqual({r[0] for r in db.execute(f"SELECT assigned_to FROM tasks WHERE id IN ({ids[1]},{ids[2]})")}, {"TI"})
        pagina = self.client.get("/eventos/1/checklist").get_data(as_text=True)
        self.assertIn("Nota de teste", pagina)

    def test_eventos_com_abas_e_triagem_antiga(self):
        pagina = self.client.get("/eventos?aba=todos").get_data(as_text=True)
        self.assertIn("Para triar", pagina)
        self.assertIn("Evento de teste", pagina)
        resposta = self.client.get("/triagem")
        self.assertEqual(resposta.status_code, 302)
        self.assertIn("aba=triar", resposta.headers["Location"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
