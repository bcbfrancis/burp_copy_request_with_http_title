from burp import IBurpExtender, IContextMenuFactory, IHttpRequestResponse
from java.io import PrintWriter
from java.util import ArrayList
from javax.swing import JMenuItem
from java.awt import Toolkit
from java.awt.datatransfer import StringSelection
from javax.swing import JOptionPane
import threading
import time
import json
from xml.dom.minidom import parseString

class BurpExtender(IBurpExtender, IContextMenuFactory, IHttpRequestResponse):

    def __init__(self):
        self.clipboard_lock = threading.Lock()

    CUT_TEXT = "[...]"

    def str_to_array(self, string):
        return [ord(c) for c in string]

    def registerExtenderCallbacks(self, callbacks):
        callbacks.setExtensionName("Copy HTTP Request & Response")

        stdout = PrintWriter(callbacks.getStdout(), True)
        stderr = PrintWriter(callbacks.getStderr(), True)

        self.helpers = callbacks.getHelpers()
        self.callbacks = callbacks
        callbacks.registerContextMenuFactory(self)

    # Implement IContextMenuFactory
    def createMenuItems(self, invocation):
        self.context = invocation
        menuList = ArrayList()
        menuList.add(JMenuItem("Copy Request2",
                               actionPerformed=self.copyRequestAndResponse))

        menuList.add(JMenuItem("Copy HTTP Request & Response (Full/Full)",
                actionPerformed=self.copyRequestFullResponseFull))
        menuList.add(JMenuItem("Copy HTTP Request & Response (Full/Header)",
                actionPerformed=self.copyRequestFullResponseHeader))
        menuList.add(JMenuItem("Copy HTTP Request & Response (Full/Header + Selected Data)",
                actionPerformed=self.copyRequestFullResponseHeaderData))

        return menuList


    def copyRequestAndResponse(self, event):
        httpTraffic = self.context.getSelectedMessages()[0]
        httpRequest = httpTraffic.getRequest()
        httpResponse = httpTraffic.getResponse()

        # Function to pretty-print XML if detected in a string
        def pretty_xml(input_str):
            try:
                xml = parseString(input_str)
                return xml.toprettyxml(indent="    ")  # 4 spaces for consistency with JSON formatting
            except Exception:
                return input_str

        # Check and format XML in JSON body
        def format_json_body(body):
            try:
                json_data = json.loads(body)
                for key, value in json_data.items():
                    if isinstance(value, str) and value.startswith('<') and value.endswith('>'):
                        json_data[key] = pretty_xml(value)
                return json.dumps(json_data, indent=4)
            except json.JSONDecodeError:
                return body

        # Splitting headers and body for the request
        requestHeaders, requestBody = self.helpers.bytesToString(httpRequest).split('\r\n\r\n', 1)
    
        data = self.str_to_array("HTTP Request:")
        data.append(13)
        data.extend(self.str_to_array(requestHeaders))
        data.append(13)
        data.append(13)
        
        # Pretty-print JSON in HTTP request body if it's JSON, else append original
        try:
            prettyJson = format_json_body(requestBody)
            data.extend(self.str_to_array(prettyJson))
        except json.JSONDecodeError:
            data.extend(self.str_to_array(requestBody))

        data.append(13)
        data.append(13)
        data.extend(self.str_to_array("HTTP Response:"))
        data.append(13)

        # Splitting headers and body for the response
        responseHeaders, responseBody = self.helpers.bytesToString(httpResponse).split('\r\n\r\n', 1)
        data.extend(self.str_to_array(responseHeaders))
        data.append(13)
        data.append(13)

        # Pretty-print JSON in HTTP response body if it's JSON, else append original
        try:
            prettyJson = format_json_body(responseBody)
            data.extend(self.str_to_array(prettyJson))
        except json.JSONDecodeError:
            data.extend(self.str_to_array(responseBody))

        self.copyToClipboard(data)






    def copyRequestFullResponseFull(self, event):
        httpTraffic = self.context.getSelectedMessages()[0]
        httpRequest = httpTraffic.getRequest()
        httpResponse = httpTraffic.getResponse()

        data = self.stripTrailingNewlines(httpRequest)
        data.append(13) # Line Break
        data.append(13)
        data.extend(self.stripTrailingNewlines(httpResponse))

        self.copyToClipboard(data)

    def copyRequestFullResponseHeader(self, event):
        httpTraffic = self.context.getSelectedMessages()[0]
        httpRequest = httpTraffic.getRequest()
        httpResponse = httpTraffic.getResponse()
        httpResponseBodyOffset = self.helpers.analyzeResponse(httpResponse).getBodyOffset()

        data = self.stripTrailingNewlines(httpRequest)
        data.append(13)
        data.append(13)
        data.extend(httpResponse[0:httpResponseBodyOffset])
        data.extend(self.str_to_array(self.CUT_TEXT))

        self.copyToClipboard(data)

    def copyRequestFullResponseHeaderData(self, event):
        httpTraffic = self.context.getSelectedMessages()[0]
        httpRequest = httpTraffic.getRequest()
        httpResponse = httpTraffic.getResponse()
        httpResponseBodyOffset = self.helpers.analyzeResponse(httpResponse).getBodyOffset()
        selectionBounds = self.context.getSelectionBounds()
        httpResponseData = httpResponse[selectionBounds[0]:selectionBounds[1]]

        data = self.stripTrailingNewlines(httpRequest)
        data.append(13)
        data.append(13)
        data.extend(httpResponse[0:httpResponseBodyOffset])
        data.extend(self.str_to_array(self.CUT_TEXT))
        data.append(13)
        data.extend(self.stripTrailingNewlines(httpResponseData))
        data.append(13)
        data.extend(self.str_to_array(self.CUT_TEXT))

        # Ugly hack because VMware is messing up the clipboard if a text is still selected, the function
        # has to be run in a separate thread which sleeps for 1.5 seconds.
        t = threading.Thread(target=self.copyToClipboard, args=(data,True))
        t.start()

    def copyToClipboard(self, data, sleep=False):
        if sleep is True:
            time.sleep(1.5)

        # Fix line endings of the headers
        data = self.helpers.bytesToString(data).replace('\r\n', '\n')

        with self.clipboard_lock:
            systemClipboard = Toolkit.getDefaultToolkit().getSystemClipboard()
            systemSelection = Toolkit.getDefaultToolkit().getSystemSelection()
            transferText = StringSelection(data)
            systemClipboard.setContents(transferText, None)
            systemSelection.setContents(transferText, None)

    def stripTrailingNewlines(self, data):
        while data[-1] in (10, 13):
            data = data[:-1]
        return data
