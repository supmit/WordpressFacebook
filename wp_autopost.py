import os, sys, re, time, gzip
import urllib, urllib2, httplib
from BeautifulSoup import BeautifulSoup
from urlparse import urlparse, urlsplit
from StringIO import StringIO
import datetime, mimetools
import xlrd
import random


"""
Some utility function definitions
"""
def urlEncodeString(s):
    tmphash = {'str' : s }
    encodedStr = urllib.urlencode(tmphash)
    encodedPattern = re.compile(r"^str=(.*)$")
    encodedSearch = encodedPattern.search(encodedStr)
    encodedStr = encodedSearch.groups()[0]
    encodedStr = encodedStr.replace('.', '%2E')
    encodedStr = encodedStr.replace('-', '%2D')
    encodedStr = encodedStr.replace(',', '%2C')
    return (encodedStr)


def encode_multipart_formdata(fields):
    BOUNDARY = mimetools.choose_boundary()
    CRLF = '\r\n'
    L = []
    for (key, value) in fields.iteritems():
        L.append('--' + BOUNDARY)
        L.append('Content-Disposition: form-data; name="%s"' % key)
        L.append('')
        L.append(value)
    L.append('--' + BOUNDARY + '--')
    L.append('')
    body = CRLF.join(L)
    content_type = 'multipart/form-data; boundary=%s' % BOUNDARY
    content_length = str(len(body))
    return content_type, content_length, body


def getTimeStampString():
    ts = time.time()
    ts_str = int(ts).__str__()
    return (ts_str)


class NoRedirectHandler(urllib2.HTTPRedirectHandler):
    def http_error_302(self, req, fp, code, msg, headers):
        infourl = urllib.addinfourl(fp, headers, req.get_full_url())
        infourl.status = code
        infourl.code = code
        return infourl

    http_error_300 = http_error_302
    http_error_301 = http_error_302
    http_error_303 = http_error_302
    http_error_307 = http_error_302 




class WordPressAutoPostBot(object):
    absUrlPattern = re.compile(r"^https?:\/\/", re.IGNORECASE)
    htmlTagPattern = re.compile(r"<[^>]+>", re.MULTILINE | re.DOTALL)
    newlinePattern = re.compile(r"\n")
    multipleWhitespacePattern = re.compile(r"\s+")
    pathEndingWithSlashPattern = re.compile(r"\/$")
    emptyStringPattern = re.compile(r"^\s*$", re.MULTILINE | re.DOTALL)

    htmlEntitiesDict = {'&nbsp;' : ' ', '&#160;' : ' ', '&amp;' : '&', '&#38;' : '&', '&lt;' : '<', '&#60;' : '<', '&gt;' : '>', '&#62;' : '>', '&apos;' : '\'', '&#39;' : '\'', '&quot;' : '"', '&#34;' : '"'}
    # Set DEBUG to False on prod env
    DEBUG = True


    def __init__(self, siteUrl):
        self.opener = urllib2.build_opener() # This is my normal opener....
        self.no_redirect_opener = urllib2.build_opener(urllib2.HTTPHandler(), urllib2.HTTPSHandler(), NoRedirectHandler()) # this one won't handle redirects.
        self.debug_opener = urllib2.build_opener(urllib2.HTTPHandler(debuglevel=1))
        # Initialize some object properties.
        self.sessionCookies = ""
        self.httpHeaders = { 'User-Agent' : r'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/27.0.1453.110 Safari/537.36',  'Accept' : 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Language' : 'en-US,en;q=0.8', 'Accept-Encoding' : 'gzip,deflate,sdch', 'Connection' : 'keep-alive', 'Host' : '' }
        self.homeDir = os.getcwd()
        self.websiteUrl = siteUrl
        self.xmlrpcUrl = self.websiteUrl + "/xmlrpc.php"
        self.xmlContent = ""
        self.requestUrl = self.websiteUrl
        self.baseUrl = None
        self.pageRequest = None
        if self.websiteUrl:
            parsedUrl = urlparse(self.requestUrl)
            self.baseUrl = parsedUrl.scheme + "://" + parsedUrl.netloc
            self.httpHeaders['Host'] = parsedUrl.netloc
            # Here we just get the webpage pointed to by the website URL
            self.pageRequest = urllib2.Request(self.requestUrl, None, self.httpHeaders)
        self.pageResponse = None
        self.requestMethod = "GET"
        self.postData = {}
        self.sessionCookies = None
        self.currentPageContent = None
        if self.websiteUrl:
            try:
                self.pageResponse = self.no_redirect_opener.open(self.pageRequest)
                self.sessionCookies = self.__class__._getCookieFromResponse(self.pageResponse)
                self.httpHeaders["Cookie"] = self.sessionCookies
            except:
                print __file__.__str__() + ": Couldn't fetch page due to limited connectivity. Please check your internet connection and try again - %s\n"%(sys.exc_info()[1].__str__())
	    	return(None)
            self.httpHeaders["Referer"] = self.requestUrl
            self.httpHeaders["Origin"] = self.websiteUrl
            self.httpHeaders["Content-Type"] = 'application/xml'
            # Initialize the account related variables...
            self.currentPageContent = self.__class__._decodeGzippedContent(self.getPageContent())
            if not self.currentPageContent:
                print "Could not access the website content of " + self.websiteUrl

        

    """
    Cookie extractor method to get cookie values from the HTTP response objects. (class method)
    """
    def _getCookieFromResponse(cls, lastHttpResponse):
        cookies = ""
        lastResponseHeaders = lastHttpResponse.info()
        responseCookies = lastResponseHeaders.getheaders("Set-Cookie")
        pathCommaPattern = re.compile(r"path=/\s*;?", re.IGNORECASE)
        domainPattern = re.compile(r"Domain=[^;]+;?", re.IGNORECASE)
        expiresPattern = re.compile(r"Expires=[^;]+;?", re.IGNORECASE)
	deletedPattern = re.compile(r"=deleted;", re.IGNORECASE)
        if responseCookies.__len__() >= 1:
            for cookie in responseCookies:
                cookieParts = cookie.split("Path=/")
                cookieParts[0] = re.sub(domainPattern, "", cookieParts[0])
                cookieParts[0] = re.sub(expiresPattern, "", cookieParts[0])
		deletedSearch = deletedPattern.search(cookieParts[0])
		if deletedSearch:
		    continue
                cookies += "; " + cookieParts[0]
	    multipleWhiteSpacesPattern = re.compile(r"\s+")
	    cookies = re.sub(multipleWhiteSpacesPattern, " ", cookies)
	    multipleSemicolonsPattern = re.compile(";\s*;")
	    cookies = re.sub(multipleSemicolonsPattern, "; ", cookies)
	    if re.compile("^\s*;").search(cookies):
		cookies = re.sub(re.compile("^\s*;"), "", cookies)
            return(cookies)
	else:
	    return(None)
    
    _getCookieFromResponse = classmethod(_getCookieFromResponse)


    def _decodeGzippedContent(cls, encoded_content):
        response_stream = StringIO(encoded_content)
        decoded_content = ""
        try:
            gzipper = gzip.GzipFile(fileobj=response_stream)
            decoded_content = gzipper.read()
        except: # Maybe this isn't gzipped content after all....
            decoded_content = encoded_content
        return(decoded_content)

    _decodeGzippedContent = classmethod(_decodeGzippedContent)


    def getPageContent(self):
        if self.pageResponse:
            content = self.pageResponse.read()
            self.currentPageContent = content
            # Remove the line with 'DOCTYPE html PUBLIC' string. It sometimes causes BeautifulSoup to fail in parsing the html
            #self.currentPageContent = re.sub(r"<.*DOCTYPE\s+html\s+PUBLIC[^>]+>", "", content)
            return(self.currentPageContent)
        else:
            return None

    def submitPost(self, postUser, postPasswd, postHeader, postCategory, postContent):
        self.xmlContent = """<?xml version='1.0'?><methodCall><methodName>wp.newPost</methodName><params><param><value><int>1</int></value></param><param>
                    <value><string>%s</string></value></param><param><value><string>%s</string></value></param><param><value><struct><member>
                    <name>post_type</name><value><string>post</string></value></member><member>
                    <name>post_status</name><value><string>publish</string></value></member><member><name>post_title</name><value>
                    <string>%s</string></value></member><member><name>post_category</name><value><string>%s</string></value></member>
                    <member><name>post_author</name><value><int>1</int></value></member><member><name>post_excerpt</name><value><string/></value></member>
                    <member><name>post_content</name><value><string>%s</string></value></member><member><name>post_format</name><value>
                    <string/></value></member></struct></value></param></params></methodCall>"""%(postUser, postPasswd, postHeader, postCategory, postContent)
        self.httpHeaders['Content-Length'] = self.xmlContent.__len__()
        self.requestUrl = self.xmlrpcUrl
        if self.xmlrpcUrl:
            self.pageRequest = urllib2.Request(self.requestUrl, self.xmlContent, self.httpHeaders)
            try:
                self.pageResponse = self.no_redirect_opener.open(self.pageRequest)
                self.currentPageContent = self.__class__._decodeGzippedContent(self.getPageContent())
                if not self.currentPageContent:
                    print "Could not access the website content of " + self.xmlrpcUrl
                else:
                    stringMatch = re.compile(r"<string>(\d+)</string>").search(self.currentPageContent)
                    if not stringMatch:
                        return(0)
                    returnNum = stringMatch.groups()[0]
                    if returnNum > 0:
                        print "Successfully posted to wordpress website %s\nPost Id is %s\n"%(self.baseUrl, returnNum)
                        self.postId = returnNum
                        return(returnNum)
                    else:
                        print "Could not post to wordpress website %s\n"%self.baseUrl
                        self.postId = 0
                        return(0)
            except:
                print "Failed to make the XML-RPC POST call to '%s': %s\n"%(self.xmlrpcUrl, sys.exc_info()[1].__str__())
        else:
            pass


    def getPostLink(self, postId, postUser, postPasswd):
        self.xmlContent = """<?xml version='1.0'?><methodCall><methodName>wp.getPost</methodName><params><param><value><int>1</int></value></param><param>
                    <value><string>%s</string></value></param><param><value><string>%s</string></value></param><param><value><int>%s</int></value></param>
                    </params></methodCall>"""%(postUser, postPasswd, postId)
        self.httpHeaders['Content-Length'] = self.xmlContent.__len__()
        self.requestUrl = self.xmlrpcUrl
        if self.xmlrpcUrl:
            self.pageRequest = urllib2.Request(self.requestUrl, self.xmlContent, self.httpHeaders)
            try:
                self.pageResponse = self.no_redirect_opener.open(self.pageRequest)
                self.currentPageContent = self.__class__._decodeGzippedContent(self.getPageContent())
                linkPattern = re.compile(r"<member><name>link</name><value><string>(.*)</string></value></member>")
                linkSearch = linkPattern.search(self.currentPageContent)
                if linkSearch:
                    postUrl = linkSearch.groups()[0]
                    return postUrl
            except:
                print "Could not make getPost call to the XML-RPC server - %s\n"%(sys.exc_info()[1].__str__())
                return None


            
    def _login(self, username, password):
        pass


    def _setCategory(self, category):
        pass


    # This method logs in and selects a category for the post. Finally
    # it gets the link to the post and returns it to the caller.
    def processPost(self):
        pass

"""
Class to log on to facebook account and make a post
"""
class FacebookAutoPostBot(object):

    MAX_RECURSE_COUNTER = 6
    def __init__(self, siteUrl = "http://www.facebook.com/"):
        self.opener = urllib2.build_opener() # This is my normal opener....
        self.no_redirect_opener = urllib2.build_opener(urllib2.HTTPHandler(), urllib2.HTTPSHandler(), NoRedirectHandler()) # this one won't handle redirects.
        #self.debug_opener = urllib2.build_opener(urllib2.HTTPHandler(debuglevel=1))
        # Initialize some object properties.
        self.sessionCookies = ""
        self.httpHeaders = { 'User-Agent' : r'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/27.0.1453.110 Safari/537.36',  'Accept' : 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Language' : 'en-US,en;q=0.8', 'Accept-Encoding' : 'gzip,deflate,sdch', 'Connection' : 'keep-alive', 'Host' : '' }
        self.homeDir = os.getcwd()
        self.websiteUrl = siteUrl
        self.requestUrl = self.websiteUrl
        self.baseUrl = None
        self.pageRequest = None
        if self.websiteUrl:
            parsedUrl = urlparse(self.requestUrl)
            self.baseUrl = parsedUrl.scheme + "://" + parsedUrl.netloc
            self.httpHeaders['Host'] = parsedUrl.netloc
            self.httpHeaders['Cookie'] = "wd=1366x381" #God knows why it is set... FB has a liking for it.
            # Here we just get the webpage pointed to by the website URL
            self.pageRequest = urllib2.Request(self.requestUrl, None, self.httpHeaders)
        self.pageResponse = None
        self.requestMethod = "GET"
        self.postData = {}
        self.sessionCookies = None
        self.currentPageContent = None
        if self.websiteUrl:
            try:
                self.pageResponse = self.no_redirect_opener.open(self.pageRequest)
                self.sessionCookies = self.__class__._getCookieFromResponse(self.pageResponse)
                self.httpHeaders["Cookie"] = self.sessionCookies
            except:
                print __file__.__str__() + ": Couldn't fetch page due to limited connectivity. Please check your internet connection and try again - %s\n"%(sys.exc_info()[1].__str__())
	    	return(None)
            self.httpHeaders["Referer"] = self.requestUrl
            self.httpHeaders["Origin"] = self.websiteUrl
            responseHeaders = self.pageResponse.info()
            if responseHeaders.has_key("Location"):
                self.requestUrl = responseHeaders['Location']
                self.pageRequest = urllib2.Request(self.requestUrl, None, self.httpHeaders)
                try:
                    self.pageResponse = self.no_redirect_opener.open(self.pageRequest)
                    self.sessionCookies = self.__class__._getCookieFromResponse(self.pageResponse)
                    self.httpHeaders["Cookie"] += self.sessionCookies
                except:
                    print __file__.__str__() + ": Couldn't fetch page due to limited connectivity. Please check your internet connection and try again - %s\n"%(sys.exc_info()[1].__str__())
                    return(None)
            self.currentPageContent = self.__class__._decodeGzippedContent(self.getPageContent())
            if not self.currentPageContent:
                print "Could not access the website content of " + self.websiteUrl
                return(None)


        """
    Cookie extractor method to get cookie values from the HTTP response objects. (class method)
    """
    def _getCookieFromResponse(cls, lastHttpResponse):
        cookies = ""
        lastResponseHeaders = lastHttpResponse.info()
        responseCookies = lastResponseHeaders.getheaders("Set-Cookie")
        expiresPattern = re.compile(r"expires=([^;]*);", re.IGNORECASE)
        pathCommaPattern = re.compile(r"path=/\s*;?", re.IGNORECASE)
        securePattern = re.compile(r"secure;?", re.IGNORECASE)
        httponlyPattern = re.compile(r"httponly;?", re.IGNORECASE)
	deletedPattern = re.compile(r"=deleted;", re.IGNORECASE)
        if responseCookies.__len__() >= 1:
            for cookie in responseCookies:
                cookieParts = cookie.split("path=/;")
                cookieParts[0] = re.sub(securePattern, "", cookieParts[0])
                cookieParts[0] = re.sub(httponlyPattern, "", cookieParts[0])
                cookieParts[0] = re.sub(expiresPattern, "", cookieParts[0])
		deletedSearch = deletedPattern.search(cookieParts[0])
		if deletedSearch:
		    continue
                cookies += "; " + cookieParts[0]
	    multipleWhiteSpacesPattern = re.compile(r"\s+")
	    cookies = re.sub(multipleWhiteSpacesPattern, " ", cookies)
	    multipleSemicolonsPattern = re.compile(";\s*;")
	    cookies = re.sub(multipleSemicolonsPattern, "; ", cookies)
	    if re.compile("^\s*;").search(cookies):
		cookies = re.sub(re.compile("^\s*;"), "", cookies)
            return(cookies)
	else:
	    return(None)
    
    _getCookieFromResponse = classmethod(_getCookieFromResponse)


    def _decodeGzippedContent(cls, encoded_content):
        response_stream = StringIO(encoded_content)
        decoded_content = ""
        try:
            gzipper = gzip.GzipFile(fileobj=response_stream)
            decoded_content = gzipper.read()
        except: # Maybe this isn't gzipped content after all....
            decoded_content = encoded_content
        return(decoded_content)

    _decodeGzippedContent = classmethod(_decodeGzippedContent)


    def getPageContent(self):
        if self.pageResponse:
            content = self.pageResponse.read()
            self.currentPageContent = content
            # Remove the line with 'DOCTYPE html PUBLIC' string. It sometimes causes BeautifulSoup to fail in parsing the html
            #self.currentPageContent = re.sub(r"<.*DOCTYPE\s+html\s+PUBLIC[^>]+>", "", content)
            return(self.currentPageContent)
        else:
            return None



    def login(self, username, password):
        # First, get all hidden and other form element variables from "login_form".
        soup = BeautifulSoup(self.currentPageContent)
        login_form = soup.find("form", {'id' : 'login_form'})
        if not login_form:
            print "Could not find login form: Possibly we are not at the facebook login page.\n"
            sys.exit()
        self.requestUrl = login_form['action']
        loginFormElements = {}
        hiddenElements = login_form.findAll("input", {'type' : 'hidden'})
        for element in hiddenElements:
            loginFormElements[element['name']] = element['value']
        loginFormElements['email'] = username
        loginFormElements['pass'] = password
        for elementName in loginFormElements.keys():
            if elementName == "lgnjs":
                loginFormElements[elementName] = int(time.time()) + (30*60)
            if elementName == "timezone":
                loginFormElements[elementName] = "-330"
        loginData = urllib.urlencode(loginFormElements)
        loginHeaders = self.httpHeaders
        loginHeaders['Cache-Control'] = "max-age=0"
        loginHeaders['Content-Type'] = "application/x-www-form-urlencoded"
        loginHeaders['Origin'] = "https://www.facebook.com"
        loginHeaders['Referer'] = "https://www.facebook.com/"
        loginHeaders['Content-Length'] = loginData.__len__()
        self.pageRequest = urllib2.Request(self.requestUrl, loginData, loginHeaders)
        try:
            self.pageResponse = self.no_redirect_opener.open(self.pageRequest)
            self.sessionCookies = self.__class__._getCookieFromResponse(self.pageResponse)
            self.httpHeaders["Cookie"] += self.sessionCookies
            loginHeaders['Cookie'] = self.httpHeaders["Cookie"]
            loginHeaders['Referer'] = "https://www.facebook.com/"
            responseHeaders = self.pageResponse.info()
            for hdr in responseHeaders.keys():
                if hdr == "Location":
                    self.requestUrl = responseHeaders[hdr]
            loginHeaders.pop("Content-Length")
            loginHeaders.pop("Content-Type")
            self.pageRequest = urllib2.Request(self.requestUrl, None, loginHeaders)
            try:
                self.pageResponse = self.no_redirect_opener.open(self.pageRequest)
                self.currentPageContent = self.__class__._decodeGzippedContent(self.getPageContent())
            except:
                print __file__.__str__() + ": Couldn't fetch page due to limited connectivity. Please check your internet connection and try again - %s\n"%(sys.exc_info()[1].__str__())
                return(None)
        except:
             print __file__.__str__() + ": Couldn't fetch page due to limited connectivity. Please check your internet connection and try again - %s\n"%(sys.exc_info()[1].__str__())
             return(None)
        responseHeaders = self.pageResponse.info()
        if responseHeaders.has_key('Location'):
            self.requestUrl = responseHeaders['Location']
            self.pageRequest = urllib2.Request(self.requestUrl, None, loginHeaders)
            try:
                self.pageResponse = self.no_redirect_opener.open(self.pageRequest)
                self.currentPageContent = self.__class__._decodeGzippedContent(self.getPageContent())
            except:
                print __file__.__str__() + ": Couldn't fetch page due to limited connectivity. Please check your internet connection and try again - %s\n"%(sys.exc_info()[1].__str__())
                return(None)
        else:
            print "Could not login - Something went wrong during the final redirection step. Please contact the programmer responsible for this code."
            print "You might be seeing this message due to facebook's response to your request with an account verification screen. "
            print "You can check this by trying to log in manually into this facebook account. Run this program after performing this manual step."
            return(None)
        return(self.currentPageContent) # At this point we are logged in.



    def logout(self):
        pass


    """
    Posts the 'message' on the user's personal home page.
    """
    def postMessage(self, message):
        commentStartPattern = re.compile(r"<!--")
        commentEndPattern = re.compile(r"-->")
        self.currentPageContent = re.sub(commentStartPattern, "", self.currentPageContent)
        self.currentPageContent = re.sub(commentEndPattern, "", self.currentPageContent)
        soup = BeautifulSoup(self.currentPageContent)
        updateStatusForm = soup.find("form", {'action' : '/ajax/updatestatus.php'})
        if not updateStatusForm:
            print "Could not spot the updatestatus form"
            return None # Something has gone wrong
        allHiddenInputs = updateStatusForm.findAll("input", {'type' : 'hidden'})
        formData = {}
        formData['xhpc_message_text'] = message
        formData['xhpc_message'] = message
        for hiddenInput in allHiddenInputs:
            if hiddenInput.has_key('value') and hiddenInput.has_key('name'):
                formData[hiddenInput['name']] = hiddenInput['value']
            elif hiddenInput.has_key('id'):
                formData[hiddenInput['id']] = ""
            else:
                pass # We won't handle HTML elements that have neither a name nor an id.
        formData['composer_session_id'] = int(time.time())
        self.requestUrl = "https://www.facebook.com/ajax/updatestatus.php"
        postData = urllib.urlencode(formData)
        postHeaders = self.httpHeaders
        postHeaders['Content-Length'] = postData.__len__()
        postHeaders['Content-Type'] = "application/x-www-form-urlencoded"
        postHeaders['Accept'] = "*/*"
        postHeaders['x-svn-ref'] = "891315"
        postHeaders['Origin'] = "https://www.facebook.com"
        self.pageRequest = urllib2.Request(self.requestUrl, postData, postHeaders)
        try:
            self.pageResponse = self.no_redirect_opener.open(self.pageRequest)
            self.currentPageContent = self.__class__._decodeGzippedContent(self.getPageContent())
            self.sessionCookies = self.__class__._getCookieFromResponse(self.pageResponse)
            self.httpHeaders["Cookie"] += self.sessionCookies
            responseHeaders = self.pageResponse.info()
            if responseHeaders.has_key("Location"):
                self.requestUrl = responseHeaders['Location']
                self.pageRequest = urllib2.Request(self.requestUrl, None, self.httpHeaders)
                try:
                    self.pageResponse = self.no_redirect_opener.open(self.pageRequest)
                    self.currentPageContent = self.__class__._decodeGzippedContent(self.getPageContent())
                    print "Posted URL '%s' on facebook\n"%(message)
                    return(self.currentPageContent)
                except:
                    print "Could not redirect after posting message. Manually verify if the message was successfully posted: %s\n"%sys.exc_info()[1].__str__()
                    return(self.currentPageContent)
            else:
                return(self.currentPageContent)
            return(self.currentPageContent)
        except:
            print "Could not post the message URL on facebook - %s\n"%sys.exc_info()[1].__str__()
            return (None)


    """
    Navigates to the page specified by 'pageUrl' and posts the 'message' there.
    """
    def postMessageOnPage(self, pageUrl, message):
        # Get the cookies from the last HTTP response recieved
        self.sessionCookies = self.__class__._getCookieFromResponse(self.pageResponse)
        self.httpHeaders["Cookie"] += self.sessionCookies
        self.httpHeaders['Referer'] = self.requestUrl
        self.requestUrl = pageUrl
        self.httpHeaders['Connection'] = "keep-alive"
        self.pageRequest = urllib2.Request(self.requestUrl, None, self.httpHeaders)
        while True:
            try:
                self.pageResponse = self.no_redirect_opener.open(self.pageRequest)
                self.currentPageContent = self.__class__._decodeGzippedContent(self.getPageContent())
                self.sessionCookies = self.__class__._getCookieFromResponse(self.pageResponse)
                self.httpHeaders["Cookie"] += self.sessionCookies
                responseHeaders = self.pageResponse.info()
                if responseHeaders.has_key("Location") or responseHeaders.has_key("location"):
                    self.requestUrl = responseHeaders['Location']
                    self.pageRequest = urllib2.Request(self.requestUrl, None, self.httpHeaders)
                    continue
                else:
                    break
            except:
                print "Could not redirect while navigating to the page '%s': %s\n"%(pageUrl, sys.exc_info()[1].__str__())
                return (None)
        self.httpHeaders['Referer'] = self.requestUrl
        # Make a POST request to actually post the message. Before that get the form variables from the message form.
        commentStartPattern = re.compile(r"<!--")
        commentEndPattern = re.compile(r"-->")
        tries = 0
        hiddenData = {}
        while True:
            self.currentPageContent = re.sub(commentStartPattern, "", self.currentPageContent)
            self.currentPageContent = re.sub(commentEndPattern, "", self.currentPageContent)
            soup = BeautifulSoup(self.currentPageContent)
            form = soup.find("form", {'action' : '/ajax/updatestatus.php'})
            if form:
                allHiddenFields = form.findAll("input", {'type' : 'hidden'})
                for hiddenField in allHiddenFields:
                    if hiddenField.has_key('name') and hiddenField.has_key('value'):
                        hiddenData[hiddenField['name']] = hiddenField['value']
                    elif hiddenField.has_key('name'):
                        hiddenData[hiddenField['name']] = ""
                    else:
                        pass
                break
            else:
                print "Could not find the page with the post form... Retrying..."
                self.pageResponse = self.no_redirect_opener.open(self.pageRequest)
                self.currentPageContent = self.__class__._decodeGzippedContent(self.getPageContent())
                tries += 1
                if tries == 2:
                    break
                continue
        hiddenData['xhpc_message_text'] = message
        hiddenData['xhpc_message'] = message
        hiddenData['composer_session_id'] = int(time.time()).__str__()
        hiddenData['disable_location_sharing'] = "false"
        postData = urllib.urlencode(hiddenData)
        self.requestUrl = "https://www.facebook.com/ajax/updatestatus.php"
        self.httpHeaders['Referer'] = "https://www.facebook.com"
        self.httpHeaders['Accept'] = "*/*"
        self.httpHeaders['Content-Type'] = "application/x-www-form-urlencoded"
        self.httpHeaders['Content-Length'] = postData.__len__()
        self.pageRequest = urllib2.Request(self.requestUrl, postData, self.httpHeaders)
        recurseCtr = 0
        while True:
            recurseCtr += 1
            if recurseCtr >= self.__class__.MAX_RECURSE_COUNTER:
                break
            try:
                self.pageResponse = self.no_redirect_opener.open(self.pageRequest)
                responseHeaders = self.pageResponse.info()
                if responseHeaders.has_key("Location"):
                    self.requestUrl = responseHeaders['Location']
                    self.pageRequest = urllib2.Request(self.requestUrl, None, self.httpHeaders)
                    continue
                else:
                    break
            except:
                print "Encountered problems while posting message. Please check if the message has been posted. - %s\n"%(sys.exc_info()[1].__str__())
                break
        if recurseCtr >= self.__class__.MAX_RECURSE_COUNTER:
            print "Recurse counter value exceeded %s. Probably got stuck in unending loop of HTTP requests/responses."%self.__class__.MAX_RECURSE_COUNTER.__str__()
            return(self.currentPageContent)
        try:
            self.currentPageContent = self.__class__._decodeGzippedContent(self.getPageContent())
        except:
            print "Could not read the contents - %s\n"%sys.exc_info()[1].__str__()
            print "But your message has been successfully posted.\n"
            return ("")
        self.httpHeaders['Referer'] = self.requestUrl
        return(self.currentPageContent)




# Class to read XLS file and extract desired information from it.
# Rules:
# All posts come from the same excel file. The data in the excel file is arranged in the following way:
# Cell A1 : wordpress website userId
# Cell B1 : Wordpress website password
# Cell C1 : Category info
# Cell D1 : Post title
# Cell E1 : Post Content
# Cell F1 : Post excerpt (optional)
# Cell G1 : Post author (optional)
# Cell H1 : Wordpress website URL (very important)
# Cell I1 : Facebook username
# Cell J1 : Facebook password
# Cell K1 : URL of the Facebook page where the link is to be posted.
# Each post will be in a row of its own. Thus, there will be separate posts in
# rows 2, 3, 4... etc. The excel reader component reads the excel file and stores
# it in a internal data structure for further usage.
#
# A Note on Scheduling:
# =====================
# The schedule of a facebook post is specified in the 12th column of the input data
# spreadsheet (Column L). Schedule may be specified in 2 formats: i) absolute date and
# time format, and ii) Relative time format. In case of "i", the date/time of the
# post is specified in "dd/mm/yyyy hh:mm:ss" format, where dd, mm, yyyy, hh, mm and ss
# are the date, month, year, hour, minute and second respectively. In case of "ii",
# the time interval between the post and the start time of the application are specified
# in seconds. If no schedule is specified, it is assumed to be sceduled for post at
# the present instant (ie., whenever the flow of control reaches that line of code.)
# The records should be arranged in the input file in such a way that the first record
# should be scheduled first and the consecutive records are scheduled in increasing
# order of time.

class Runner(object):

    SLEEP_INTERVAL = 10 # The system will sleep for these many seconds every time it is sent to sleep.
    def __init__(self, xlsFile):
        self.book = xlrd.open_workbook(xlsFile)
        self.sheet = self.book.sheet_by_index(0)


    def run(self):
        data = {'userId' : '', 'passwd' : '', 'siteUrl' : '', 'postTitle' : '', 'postContent' : '', 'postExcerpt' : '', 'postAuthor' : '', 'category' : '', 'fbWord1' : '', 'fbWord2' : '', 'fbWord3' : '', 'fbPageLink' : '', 'fbSchedule' : ''}
        nrow = 0
        fbActionList = []
        progStartTime = int(time.time())
        while nrow < self.sheet.nrows:
            ncol = 0
            data = {}
            while ncol < self.sheet.ncols:
                cell_value = self.sheet.cell_value(nrow, ncol)
                if ncol == 0:
                    data['userId'] = cell_value.__str__()
                    if data['userId'] == "":
                        break
                elif ncol == 1:
                    data['passwd'] = cell_value
                elif ncol == 2:
                    data['category'] = cell_value
                elif ncol == 3:
                    data['postTitle'] = cell_value
                elif ncol == 4:
                    data['postContent'] = cell_value
                elif ncol == 5:
                    data['postExcerpt'] = cell_value
                elif ncol == 6:
                    data['postAuthor'] = cell_value
                elif ncol == 7:
                    data['siteUrl'] = cell_value
                elif ncol == 8:
                    data['fbUserName'] = cell_value
                elif ncol == 9:
                    data['fbPassword'] = cell_value
                elif ncol == 10:
                    data['fbPageLink'] = cell_value
                elif ncol == 11:
                    data['fbSchedule'] = cell_value
                    if re.compile(r"\d{1,2}\/\d{1,2}\/\d{4}\s+\d{1,2}:\d{1,2}:\d{1,2}").search(data['fbSchedule'].__str__()):
                        data['fbSchedule'] = data['fbSchedule'] # Strange assignment
                    else:
                        data['fbSchedule'] = datetime.datetime.fromtimestamp(progStartTime + data['fbSchedule']).strftime('%d/%m/%Y %H:%M:%S')
                    print "Facebook post scheduled at %s\n"%data['fbSchedule'].__str__()
                elif ncol == 12: # This is the first word that replaces a pattern in the variable sentence
                    data['fbWord1'] = cell_value
                    data['fbWord2'] = ""
                    data['fbWord3'] = ""
                elif ncol == 13: # This is the second word that replaces a pattern in the variable sentence
                    data['fbWord2'] = cell_value
                    data['fbWord3'] = ""
                elif ncol == 14: # This is the third word that replaces a pattern in the variable sentence
                    data['fbWord3'] = cell_value
                else:
                    pass
                ncol += 1
            if data['userId'] != "":
                combiObject = WordCombinator(( data['fbWord1'], data['fbWord2'], data['fbWord3'] ))
                varSentence = combiObject.__class__.getVarSentence("Variations.txt") # Expecting the variations file in the same directory as the script.WW
                combinedString = combiObject.combine(varSentence)
                #print combinedString
                bot = WordPressAutoPostBot(data['siteUrl'])
                bot.submitPost(data['userId'], data['passwd'], data['postTitle'], data['category'], data['postContent'])
                # At this stage we have an uncategorized published post. We need to categorize it and get a link to it.
                postUrl = bot.getPostLink(bot.postId, data['userId'], data['passwd'])
                data['wpPostURL'] = combinedString + "\n" + postUrl
                fbActionList.append(data)
            nrow += 1
        ctr = 1
        for activityData in fbActionList:
            currentInstant = datetime.datetime.fromtimestamp(int(time.time())).strftime('%d/%m/%Y %H:%M:%S')
            print "Waiting to post...\n"
            while currentInstant < activityData['fbSchedule']:
                time.sleep(self.__class__.SLEEP_INTERVAL)
                currentInstant = datetime.datetime.fromtimestamp(int(time.time())).strftime('%d/%m/%Y %H:%M:%S')
            fb = FacebookAutoPostBot()
            print "Logging into facebook account of user '%s'...\n"%activityData['fbUserName']
            content = fb.login(activityData['fbUserName'], activityData['fbPassword'])
            print "Posting the link on facebook page '%s' from account of '%s'. This might take a few minutes...\n"%(activityData['fbPageLink'], activityData['fbUserName'])
            if activityData['fbPageLink'] == "":
                postedContent = fb.postMessage(activityData['wpPostURL'])
            else:
                postedContent = fb.postMessageOnPage(activityData['fbPageLink'], activityData['wpPostURL'])
            ctr += 1


class WordCombinator(object):

    def __init__(self, words):
        self.words = words
        self.varSentence = ""
        self.combinedSentence = ""

    # Combine the words with the variable line.
    def combine(self, varSentence):
        self.combinedSentence = varSentence
        if self.words.__len__() == 0:
            print "There are no words to match the places in the variable sentence.\n"
            return ""
        varTermsDict = {
            "%%POS1%%" : self.words[0],
            "%%POS2%%" : "",
            "%%POS3%%" : "",
        }
        if self.words.__len__() >= 3:
            varTermsDict["%%POS2%%"] = self.words[1]
            varTermsDict["%%POS3%%"] = self.words[2]
        elif self.words.__len__() >= 2:
            varTermsDict["%%POS2%%"] = self.words[1]
        self.combinedSentence = re.sub(re.compile("%%POS1%%"), varTermsDict["%%POS1%%"], self.combinedSentence)
        self.combinedSentence = re.sub(re.compile("%%POS2%%"), varTermsDict["%%POS2%%"], self.combinedSentence)
        self.combinedSentence = re.sub(re.compile("%%POS3%%"), varTermsDict["%%POS3%%"], self.combinedSentence)
        return (self.combinedSentence)


    def getVarSentence(cls, variationsFile):
        fv = open(variationsFile, "r")
        varLines = fv.readlines() # Expecting 1 variable sentence per line
        fv.close()
        numLines = varLines.__len__()
        randomNum = int(numLines * random.random())
        return varLines[randomNum]

    getVarSentence = classmethod(getVarSentence)

    
if __name__ == "__main__":
    inputFilename = sys.argv[1]
    runner = Runner(inputFilename)
    runner.run()
